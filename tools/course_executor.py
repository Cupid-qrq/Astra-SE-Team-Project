"""Private course executor protocol. Python 3.6-compatible controller, not a sandbox.

All dispatch calls require an exclusive host slot lock held by the CLI.
Payloads are accepted only over the authenticated controller channel.
"""

import base64
import binascii
import hashlib
import json
import os
import re
from pathlib import Path


class ProtocolError(ValueError):
    pass


class ExecutionRequest:
    def __init__(self, value, code, stdin):
        self.execution_id = value["execution_id"]
        self.request_hash = value["request_hash"]
        self.image = value["image"]
        self.language = value["language"]
        self.code = code
        self.stdin = stdin
        self.timeout_ms = value.get("timeout_ms", 40000)
        self.fingerprint = hashlib.sha256(
            json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    def __repr__(self):
        return f"ExecutionRequest(identity={self.execution_id}, language={self.language})"


def validate_request(value):
    try:
        if (
            not isinstance(value, dict)
            or set(value) - {"timeout_ms"}
            != {"operation", "execution_id", "request_hash", "image", "language", "code", "stdin"}
            or value["operation"] != "execute"
        ):
            raise ValueError
        if (
            type(value.get("timeout_ms", 40000)) is not int
            or not 1 <= value.get("timeout_ms", 40000) <= 40000
        ):
            raise ValueError
        if any(not isinstance(value[k], str) for k in value if k != "timeout_ms"):
            raise ValueError
        if any(
            re.fullmatch(r"[0-9a-f]{64}", value[k]) is None
            for k in ("execution_id", "request_hash")
        ):
            raise ValueError
        if re.fullmatch(r"sha256:[0-9a-f]{64}", value["image"]) is None or value[
            "language"
        ] not in ("cpp17", "python3"):
            raise ValueError
        decoded = []
        for key in ("code", "stdin"):
            if len(value[key]) > 87384:
                raise ValueError
            raw = base64.b64decode(value[key], validate=True)
            if len(raw) > 65536 or base64.b64encode(raw).decode() != value[key]:
                raise ValueError
            raw.decode("utf-8")
            decoded.append(raw)
        if not decoded[0]:
            raise ValueError
        return ExecutionRequest(value, *decoded)
    except (ValueError, TypeError, KeyError, binascii.Error):
        pass
    raise ProtocolError("INVALID_EXECUTION_REQUEST")


def _persist(path, value):
    temporary = path.with_suffix(".pending")
    descriptor = os.open(str(temporary), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w") as output:
        json.dump(value, output, separators=(",", ":"))
        output.flush()
        os.fsync(output.fileno())
    os.replace(str(temporary), str(path))
    if os.name == "posix":
        directory = os.open(str(path.parent), os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)


def dispatch(value, directory, execute):
    """Caller owns the slot lock. Journal contains identity/result only, never input.

    STARTED on disk is deliberately not re-executed. Recovery must fence and
    clean that identity before the worker can release the database slot.
    """
    if not isinstance(value, dict):
        raise ProtocolError("INVALID_EXECUTION_REQUEST")
    identity = value.get("execution_id")
    if not isinstance(identity, str) or re.fullmatch(r"[0-9a-f]{64}", identity) is None:
        raise ProtocolError("INVALID_EXECUTION_ID")
    root = Path(directory)
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = root / (identity + ".json")
    previous = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    if value.get("operation") == "cancel":
        if set(value) != {"operation", "execution_id"}:
            raise ProtocolError("INVALID_CANCEL_REQUEST")
        # Fence first. Physical cleanup confirmation is supplied by the CLI separately.
        _persist(path, {"state": "CANCELLED", "identity": identity})
        return {"state": "CANCELLED", "cleanup_confirmed": previous is None}
    request = validate_request(value)
    if previous is not None:
        if previous.get("state") == "CANCELLED":
            raise ProtocolError("EXECUTION_FENCED")
        if previous.get("fingerprint") != request.fingerprint:
            raise ProtocolError("EXECUTION_ID_CONFLICT")
        if previous.get("state") == "FINISHED":
            return previous["result"]
        raise ProtocolError("EXECUTION_REQUIRES_RECOVERY")
    _persist(path, {"state": "STARTED", "identity": identity, "fingerprint": request.fingerprint})
    result = execute(request)
    if not isinstance(result, dict) or result.get("cleanup_confirmed") is not True:
        raise ProtocolError("EXECUTION_CLEANUP_UNCONFIRMED")
    _persist(
        path,
        {
            "state": "FINISHED",
            "identity": identity,
            "fingerprint": request.fingerprint,
            "result": result,
        },
    )
    return result


def cpu_exceeded(nanoseconds, limit_ms):
    return type(nanoseconds) is int and nanoseconds >= limit_ms * 1000000


def diagnose(phase, exit_code, wall_timeout, overflow, oom_killed, cpu_exceeded):
    if wall_timeout or cpu_exceeded is True:
        return "TLE"
    if overflow or oom_killed:
        return "RE" if phase == "run" else "SE"
    if exit_code in (125, 126, 127, 137) or exit_code is None:
        return "SE"
    if exit_code == 0:
        return None
    return "CE" if phase == "compile" else "RE"


def execute_safely(request, execute, cleanup):
    result = {"diagnosis": "SE", "failure_code": "EXECUTION_FAILED"}
    try:
        result = execute(request)
    except (Exception, KeyboardInterrupt):
        result = {"diagnosis": "SE", "failure_code": "EXECUTION_FAILED"}
    finally:
        try:
            confirmed = cleanup(request.execution_id) is True
        except (Exception, KeyboardInterrupt):
            confirmed = False
    if not confirmed:
        return {
            "diagnosis": "SE",
            "failure_code": "CLEANUP_UNCONFIRMED",
            "cleanup_confirmed": False,
        }
    return dict(result, cleanup_confirmed=True)


def main():
    import argparse
    import fcntl
    import signal
    import sys

    import course_container_smoke as container
    import course_runtime as runtime

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    parser.add_argument("--state-dir", default="/var/lib/astra-course-executor")
    args = parser.parse_args()
    root = Path(args.state_dir)
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    value = None
    try:
        raw = sys.stdin.buffer.read(200001)
        if len(raw) > 200000:
            raise ProtocolError("REQUEST_TOO_LARGE")
        value = json.loads(raw.decode("utf-8"))
        with (root / "slot.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            signal.signal(
                signal.SIGTERM, lambda *unused: (_ for _ in ()).throw(KeyboardInterrupt())
            )
            if value.get("operation") == "cancel":
                result = dispatch(value, str(root / "journal"), runtime.execute)
                result["cleanup_confirmed"] = runtime.cleanup(value["execution_id"])
            else:
                validated = validate_request(value)
                if validated.image != args.image:
                    raise ProtocolError("IMAGE_NOT_ALLOWED")
                # Orphan resources reject new requests. Cancelling their known identity
                # remains available, and its persistent tombstone prevents delayed starts.
                container.require_clean_slot()
                result = dispatch(value, str(root / "journal"), runtime.execute)
            print(json.dumps(result, separators=(",", ":")))
            return 0
    except (Exception, KeyboardInterrupt):
        pass
    # Do not return arbitrary exception strings or a chained private-input exception.
    print(
        json.dumps(
            {"diagnosis": "SE", "failure_code": "EXECUTOR_UNAVAILABLE", "cleanup_confirmed": False}
        )
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

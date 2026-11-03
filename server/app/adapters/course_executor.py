"""Authenticated, bounded private transport to the course Podman controller.

Never call while holding a database transaction. No student program executes here.
"""

import base64
import hashlib
import json
import re
import subprocess
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from app.shared.judge import ExecutionError, sha_value

Transport = Callable[[list[str], bytes, float], bytes]


@dataclass(frozen=True)
class ExecutionResult:
    phase: str
    diagnosis: str | None
    exit_code: int | None
    stdout: bytes = field(repr=False)
    cpu_ms: int | None = None
    memory_bytes: int | None = None


def ssh_transport(command: list[str], payload: bytes, timeout: float) -> bytes:
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        shell=False,
    )
    assert process.stdin is not None and process.stdout is not None
    output = bytearray()
    overflow = threading.Event()

    def receive() -> None:
        assert process.stdout is not None
        try:
            while chunk := process.stdout.read(8192):
                if len(output) + len(chunk) > 1500000:
                    overflow.set()
                    break
                output.extend(chunk)
        finally:
            process.stdout.close()

    def send() -> None:
        assert process.stdin is not None
        try:
            process.stdin.write(payload)
            process.stdin.flush()
        except OSError:
            pass
        finally:
            process.stdin.close()

    threads = [
        threading.Thread(target=receive, daemon=True),
        threading.Thread(target=send, daemon=True),
    ]
    for thread in threads:
        thread.start()
    deadline = time.monotonic() + timeout
    ok = False
    try:
        while process.poll() is None and not overflow.is_set() and time.monotonic() < deadline:
            time.sleep(0.01)
        ok = process.poll() == 0 and not overflow.is_set()
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=5)
        for thread in threads:
            thread.join(timeout=2)
    if not ok or overflow.is_set() or any(t.is_alive() for t in threads):
        raise ExecutionError("COURSE_TRANSPORT_UNKNOWN")
    return bytes(output)


class CourseExecutor:
    def __init__(
        self,
        host: str,
        image: str,
        *,
        transport: Transport = ssh_transport,
        script: str = "/opt/astra-course-test/course_executor.py",
        state_dir: str = "/var/lib/astra-course-executor",
    ):
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,99}", host) or not re.fullmatch(
            r"sha256:[0-9a-f]{64}", image
        ):
            raise ExecutionError("INVALID_COURSE_CONFIGURATION")
        if any(
            not re.fullmatch(r"/[a-zA-Z0-9_./-]+", p) or ".." in p.split("/")
            for p in (script, state_dir)
        ):
            raise ExecutionError("INVALID_COURSE_CONFIGURATION")
        self.image = image
        self.transport = transport
        self.command = [
            "ssh",
            "-T",
            "-o",
            "BatchMode=yes",
            "-o",
            "StrictHostKeyChecking=yes",
            "-o",
            "ConnectTimeout=10",
            "-o",
            "ConnectionAttempts=1",
            "-o",
            "ServerAliveInterval=5",
            "-o",
            "ServerAliveCountMax=2",
            host,
            "python3",
            script,
            "--image",
            image,
            "--state-dir",
            state_dir,
        ]

    def _call(self, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
        result = None
        try:
            raw = self.transport(
                self.command, json.dumps(payload, separators=(",", ":")).encode(), timeout
            )
            if len(raw) > 1500000:
                raise ValueError
            value = json.loads(raw)
            if not isinstance(value, dict):
                raise ValueError
            result = value
        except Exception:
            pass
        if result is None:
            raise ExecutionError("COURSE_EXECUTION_UNKNOWN")
        return result

    def execute(
        self, identity: str, language: str, code: bytes, stdin: bytes, timeout: float = 40
    ) -> ExecutionResult:
        sha_value(identity)
        if (
            language not in ("cpp17", "python3")
            or not 1 <= len(code) <= 65536
            or len(stdin) > 65536
        ):
            raise ExecutionError("INVALID_EXECUTION_INPUT")
        body = dict(
            operation="execute",
            execution_id=identity,
            image=self.image,
            language=language,
            code=base64.b64encode(code).decode(),
            stdin=base64.b64encode(stdin).decode(),
        )
        body["request_hash"] = hashlib.sha256(
            json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        value = self._call(body, timeout)
        result = None
        try:
            if value.get("cleanup_confirmed") is not True or value.get("phase") not in (
                "COMPILE",
                "RUN",
            ):
                raise ValueError
            diagnosis = value.get("diagnosis")
            if diagnosis not in (None, "CE", "RE", "TLE", "SE"):
                raise ValueError
            exit_code = value.get("exit_code")
            if exit_code is not None and (type(exit_code) is not int or not 0 <= exit_code <= 255):
                raise ValueError
            if diagnosis is None and (exit_code != 0 or value["phase"] != "RUN"):
                raise ValueError
            if diagnosis == "CE" and value["phase"] != "COMPILE":
                raise ValueError
            for key in ("cpu_ms", "memory_bytes"):
                if value.get(key) is not None and (type(value[key]) is not int or value[key] < 0):
                    raise ValueError
            raw = base64.b64decode(value.get("stdout", ""), validate=True)
            if len(raw) > 1048576 or base64.b64encode(raw).decode() != value.get("stdout", ""):
                raise ValueError
            result = ExecutionResult(
                value["phase"],
                diagnosis,
                exit_code,
                raw,
                value.get("cpu_ms"),
                value.get("memory_bytes"),
            )
        except (ValueError, TypeError, KeyError):
            pass
        if result is None:
            raise ExecutionError("INVALID_COURSE_RESULT")
        return result

    def cancel(self, identity: str) -> bool:
        sha_value(identity)
        try:
            value = self._call(dict(operation="cancel", execution_id=identity), 15)
            return value.get("state") == "CANCELLED" and value.get("cleanup_confirmed") is True
        except ExecutionError:
            return False

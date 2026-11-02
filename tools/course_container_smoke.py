"""Single-slot Podman smoke with public fixtures; not a student-code service.

Compatible with the test host's Python 3.6. No third-party dependencies.
"""

import argparse
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
import uuid
from collections import namedtuple
from datetime import datetime, timezone
from pathlib import Path

OUTPUT_BYTES = 1048576
DIRECTORY_BYTES = 33554432
ROUND_SECONDS = 360
_deadline = None
LABEL = "org.astra.course-smoke"
Result = namedtuple("Result", "returncode stdout stderr timed_out overflow duration_ms")


class SmokeFailure(ValueError):
    def __init__(self, code):
        self.code = code if re.fullmatch(r"[A-Z_]{1,64}", code) else "SMOKE_FAILED"
        super().__init__(self.code)


def pinned_image(image):
    if not re.fullmatch(r"(?:[a-zA-Z0-9./:_-]+@)?sha256:[0-9a-f]{64}", image):
        raise SmokeFailure("PINNED_IMAGE_REQUIRED")


def owned_prefix(prefix):
    if not re.fullmatch(r"astra-course-[0-9a-f]{32}", prefix):
        raise SmokeFailure("INVALID_RESOURCE_PREFIX")


def expected_config(phase, language):
    if phase not in ("compile", "run") or language not in ("cpp17", "python3"):
        raise SmokeFailure("INVALID_PHASE_OR_LANGUAGE")
    memory = 536870912 if phase == "compile" else 268435456
    return {
        "Memory": memory,
        "MemorySwap": memory,
        "PidsLimit": 30 if phase == "compile" else 1,
        "CpuPeriod": 100000,
        "CpuQuota": 100000,
        "NetworkMode": "none",
        "IpcMode": "none",
        "ReadonlyRootfs": True,
        "CapDrop": ["ALL"],
        "SecurityOpt": ["no-new-privileges"],
    }


def restricted_args(image, name, volume, phase, language):
    pinned_image(image)
    prefix = name.rsplit("-", 1)[0]
    owned_prefix(prefix)
    if (
        name not in [prefix + "-" + role for role in ("compile", "run", "hold")]
        or volume != prefix + "-work"
    ):
        raise SmokeFailure("INVALID_RESOURCE_NAME")
    config = expected_config(phase, language)
    cpu = 20 if phase == "compile" else (2 if language == "cpp17" else 4)
    return [
        "podman",
        "create",
        "--name=" + name,
        "--label=" + LABEL + "=" + prefix,
        "--pull=never",
        "--network=none",
        "--no-hosts",
        "--hostname=astra-course",
        "--http-proxy=false",
        "--ipc=none",
        "--read-only",
        "--read-only-tmpfs=false",
        "--user=65534:65534",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        "--log-driver=none",
        "--memory=" + str(config["Memory"]),
        "--memory-swap=" + str(config["MemorySwap"]),
        "--pids-limit=" + str(config["PidsLimit"]),
        "--cpu-period=100000",
        "--cpu-quota=100000",
        f"--ulimit=cpu={cpu}:{cpu}",
        "--ulimit=fsize=1048576:1048576",
        "--ulimit=nofile=64:64",
        "--ulimit=core=0:0",
        "--workdir=/work",
        "--env=TMPDIR=/work",
        "--env=PYTHONDONTWRITEBYTECODE=1",
        "--volume",
        volume + ":/work:rw,nocopy",
        "--interactive",
        image,
    ]


def verify_config(config, phase, language, volume):
    # Compare the engine's actual inspect response, not just requested flags.
    dropped = set(config.get("CapDrop") or [])
    defaults = {
        "CAP_CHOWN",
        "CAP_DAC_OVERRIDE",
        "CAP_FOWNER",
        "CAP_FSETID",
        "CAP_KILL",
        "CAP_NET_BIND_SERVICE",
        "CAP_NET_RAW",
        "CAP_SETFCAP",
        "CAP_SETGID",
        "CAP_SETPCAP",
        "CAP_SETUID",
        "CAP_SYS_CHROOT",
    }
    if config.get("CapAdd") or not (dropped == {"ALL"} or dropped >= defaults):
        raise SmokeFailure("CONTAINER_CAPABILITY_DRIFT")
    for key, value in expected_config(phase, language).items():
        if key == "CapDrop":
            continue
        if config.get(key) != value:
            raise SmokeFailure("CONTAINER_CONFIG_DRIFT")


def remaining_timeout(timeout, deadline):
    if deadline is None:
        return timeout
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise SmokeFailure("ROUND_DEADLINE_EXCEEDED")
    return min(timeout, remaining)


def bounded_process(argv, input_bytes=b"", timeout=10, max_bytes=OUTPUT_BYTES):
    timeout = remaining_timeout(timeout, _deadline)
    started = time.monotonic()
    process = subprocess.Popen(
        argv,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
    )
    buffers = [bytearray(), bytearray()]
    lock = threading.Lock()
    exceeded = threading.Event()

    def read_stream(stream, index):
        try:
            while True:
                data = os.read(stream.fileno(), 8192)
                if not data:
                    break
                with lock:
                    remaining = max_bytes - sum(len(b) for b in buffers)
                    buffers[index].extend(data[: max(0, remaining)])
                    if len(data) > remaining:
                        exceeded.set()
        finally:
            stream.close()

    def write_input():
        try:
            process.stdin.write(input_bytes)
            process.stdin.flush()
        except (BrokenPipeError, OSError):
            pass
        finally:
            process.stdin.close()

    threads = [
        threading.Thread(target=read_stream, args=(process.stdout, 0)),
        threading.Thread(target=read_stream, args=(process.stderr, 1)),
        threading.Thread(target=write_input),
    ]
    for thread in threads:
        thread.daemon = True
        thread.start()
    timed_out = False
    try:
        while process.poll() is None:
            if exceeded.is_set() or time.monotonic() - started >= timeout:
                timed_out = not exceeded.is_set()
                process.terminate()
                try:
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    process.kill()
                break
            time.sleep(0.01)
        process.wait(timeout=2)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=2)
        for thread in threads:
            thread.join(timeout=2)
    if any(thread.is_alive() for thread in threads):
        raise SmokeFailure("CLIENT_PIPE_NOT_CLOSED")
    return Result(
        process.returncode,
        bytes(buffers[0]),
        bytes(buffers[1]),
        timed_out,
        exceeded.is_set(),
        round((time.monotonic() - started) * 1000),
    )


def control(args, input_bytes=b"", timeout=15):
    result = bounded_process(["podman"] + args, input_bytes, timeout)
    if result.returncode != 0 or result.timed_out or result.overflow:
        raise SmokeFailure("CONTAINER_CONTROL_FAILED")
    return result.stdout


def inspect_container(name):
    return json.loads(control(["inspect", name]))[0]


def verify_inspection(item, phase, language, volume):
    verify_config(item["HostConfig"], phase, language, volume)
    if item["Config"].get("User") != "65534:65534":
        raise SmokeFailure("CONTAINER_USER_DRIFT")
    mounts = item.get("Mounts", [])
    if (
        len(mounts) != 1
        or mounts[0].get("Type") != "volume"
        or mounts[0].get("Name") != volume
        or mounts[0].get("Destination") != "/work"
    ):
        raise SmokeFailure("CONTAINER_MOUNT_DRIFT")
    limits = {
        v["Name"].lower().replace("rlimit_", ""): (v["Soft"], v["Hard"])
        for v in item["HostConfig"].get("Ulimits", [])
    }
    cpu = 20 if phase == "compile" else (2 if language == "cpp17" else 4)
    if any(
        limits.get(key) != value
        for key, value in {
            "cpu": (cpu, cpu),
            "fsize": (OUTPUT_BYTES, OUTPUT_BYTES),
            "core": (0, 0),
        }.items()
    ):
        raise SmokeFailure("CONTAINER_ULIMIT_DRIFT")


def cleanup_resources(prefix):
    global _deadline
    previous = _deadline
    _deadline = None  # Cleanup must remain possible after the round's deadline.
    try:
        return _cleanup_resources(prefix)
    finally:
        _deadline = previous


def _cleanup_resources(prefix):
    owned_prefix(prefix)
    ok = True
    for role in ("run", "compile", "hold"):
        name = prefix + "-" + role
        try:
            exists = bounded_process(["podman", "container", "exists", name])
            if exists.returncode == 1 and not exists.timed_out:
                continue
            if exists.returncode != 0 or exists.timed_out or exists.overflow:
                raise SmokeFailure("UNKNOWN_CONTAINER")
            item = inspect_container(name)
            if item["Config"].get("Labels", {}).get(LABEL) != prefix:
                raise SmokeFailure("RESOURCE_NOT_OWNED")
            if item["State"].get("Running"):
                control(["kill", "--signal=KILL", name], timeout=5)
            if inspect_container(name)["State"].get("Running"):
                raise SmokeFailure("EXIT_NOT_CONFIRMED")
            control(["rm", name], timeout=5)
            if bounded_process(["podman", "container", "exists", name]).returncode != 1:
                raise SmokeFailure("REMOVAL_NOT_CONFIRMED")
        except (ValueError, KeyError, OSError):
            ok = False
    # Do not remove a shared live mount if any container's exit is unknown.
    if not ok:
        return False
    name = prefix + "-work"
    try:
        exists = bounded_process(["podman", "volume", "exists", name])
        if exists.returncode == 1 and not exists.timed_out:
            return True
        if exists.returncode != 0 or exists.timed_out or exists.overflow:
            return False
        volume = json.loads(control(["volume", "inspect", name]))[0]
        if volume.get("Labels", {}).get(LABEL) != prefix:
            return False
        control(["volume", "rm", name], timeout=5)
        check = bounded_process(["podman", "volume", "exists", name])
        return check.returncode == 1 and not check.timed_out and not check.overflow
    except (ValueError, KeyError, OSError):
        return False


def public_source(language, case):
    if language == "cpp17":
        body = {
            "normal": "int a,b;std::cin>>a>>b;std::cout<<a+b;",
            "error": "invalid syntax",
            "timeout": "std::this_thread::sleep_for(std::chrono::seconds(30));",
        }[case]
        return (
            "#include <iostream>\n#include <thread>\n#include <chrono>\nint main(){"
            + body
            + "}\n"
        ).encode()
    return {
        "normal": b"print(sum(map(int,input().split())))\n",
        "error": b"this is invalid syntax!\n",
        "timeout": b"import time\ntime.sleep(30)\n",
    }[case]


def verify_volume(actual):
    options = actual.get("Options", {})
    required = {
        "type": "tmpfs",
        "device": "tmpfs",
        "o": "size=33554432,uid=65534,gid=65534,mode=0700,nodev,nosuid",
    }
    if (
        actual.get("Driver") != "local"
        or actual.get("UID") != 65534
        or actual.get("GID") != 65534
        or any(options.get(k) != v for k, v in required.items())
    ):
        raise SmokeFailure("VOLUME_QUOTA_DRIFT")
    for key, value in {"UID": "65534", "GID": "65534", "SIZE": "33554432"}.items():
        if key in options and options[key] != value:
            raise SmokeFailure("VOLUME_QUOTA_DRIFT")


def completed_exit(result, state):
    started = state.get("StartedAt", "")
    code = state.get("ExitCode")
    if (
        not started
        or started.startswith("0001-")
        or state.get("Running") is not False
        or type(code) is not int
        or code != result.returncode
        or state.get("Error")
        or result.timed_out
        or result.overflow
    ):
        raise SmokeFailure("CONTAINER_TERMINAL_STATE_UNCONFIRMED")
    return code


def execute_case(image, prefix, language, case):
    volume = prefix + "-work"
    control(
        [
            "volume",
            "create",
            "--label=" + LABEL + "=" + prefix,
            "--opt=type=tmpfs",
            "--opt=device=tmpfs",
            "--opt=o=size=33554432,uid=65534,gid=65534,mode=0700,nodev,nosuid",
            volume,
        ]
    )
    actual = json.loads(control(["volume", "inspect", volume]))[0]
    verify_volume(actual)
    # Keep tmpfs mounted across compile exit and run start; no program executes here.
    control(
        restricted_args(image, prefix + "-hold", volume, "run", language)[1:]
        + ["/usr/bin/sleep", "360"]
    )
    control(["start", prefix + "-hold"])
    if not inspect_container(prefix + "-hold")["State"].get("Running"):
        raise SmokeFailure("WORK_VOLUME_NOT_HELD")
    extension = "cpp" if language == "cpp17" else "py"
    compile_command = (
        "/usr/bin/g++ -std=c++17 -O0 /work/main.cpp -o /work/main"
        if language == "cpp17"
        else "/usr/bin/python3 -m py_compile /work/main.py"
    )
    # Only this constant trusted command uses a shell; no user-provided text is interpolated.
    command = "cat > /work/main." + extension + "; " + compile_command
    name = prefix + "-compile"
    control(
        restricted_args(image, name, volume, "compile", language)[1:]
        + ["/bin/sh", "-c", command]
    )
    verify_inspection(inspect_container(name), "compile", language, volume)
    compiled = bounded_process(
        ["podman", "start", "--attach", "--interactive", "--sig-proxy=false", name],
        public_source(language, case),
        20,
    )
    if compiled.timed_out or compiled.overflow:
        raise SmokeFailure("COMPILE_LIMIT_OR_CONTROL_FAILURE")
    compile_exit = completed_exit(compiled, inspect_container(name)["State"])
    if compile_exit != 0:
        if case != "error" or compile_exit != 1:
            raise SmokeFailure("UNEXPECTED_COMPILE_EXIT")
        return {
            "language": language,
            "case": case,
            "stage": "compile",
            "client_exit_code": compiled.returncode,
            "container_exit_code": compile_exit,
            "passed": True,
            "config_checked": True,
        }
    if case == "error":
        raise SmokeFailure("ERROR_FIXTURE_ACCEPTED")
    name = prefix + "-run"
    command = (
        ["/work/main"] if language == "cpp17" else ["/usr/bin/python3", "/work/main.py"]
    )
    control(restricted_args(image, name, volume, "run", language)[1:] + command)
    verify_inspection(inspect_container(name), "run", language, volume)
    wall = 5 if language == "cpp17" else 10
    ran = bounded_process(
        ["podman", "start", "--attach", "--interactive", "--sig-proxy=false", name],
        b"1 2\n",
        wall,
    )
    state = inspect_container(name)["State"]
    started = state.get("StartedAt", "")
    if not started or started.startswith("0001-"):
        raise SmokeFailure("RUN_NOT_STARTED")
    passed = (
        ran.timed_out and not ran.overflow and state.get("Running") is True
        if case == "timeout"
        else completed_exit(ran, state) == 0
        and not ran.timed_out
        and not ran.overflow
        and ran.stdout.strip() == b"3"
    )
    return {
        "language": language,
        "case": case,
        "stage": "run",
        "client_exit_code": ran.returncode,
        "container_exit_code": None if state.get("Running") else state.get("ExitCode"),
        "wall_timeout": ran.timed_out,
        "duration_ms": ran.duration_ms,
        "passed": passed,
        "config_checked": True,
        "cpu_ms": None,
        "memory_bytes": None,
    }


def execute_fixtures(image, prefix):
    results = []
    for language in ("cpp17", "python3"):
        for case in ("normal", "error", "timeout"):
            try:
                results.append(execute_case(image, prefix, language, case))
            finally:
                if not cleanup_resources(prefix):
                    raise SmokeFailure("CLEANUP_NOT_CONFIRMED")
            if not results[-1]["passed"]:
                break
    return results


def run_smoke(image, source_sha, execute=execute_fixtures, cleanup=cleanup_resources):
    global _deadline
    pinned_image(image)
    if not re.fullmatch(r"[0-9a-f]{40}", source_sha):
        raise SmokeFailure("SOURCE_SHA_REQUIRED")
    prefix = "astra-course-" + uuid.uuid4().hex
    report = {
        "schema": "astra-course-container-smoke-v1",
        "performed_at": datetime.now(timezone.utc).isoformat(),  # noqa: UP017 - host Python 3.6
        "source_sha": source_sha,
        "controller_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "image": image,
        "resource_prefix": prefix,
        "slots": 1,
        "formal_execution_enabled": False,
        "passed": False,
        "cleanup_confirmed": False,
        "cases": [],
    }
    _deadline = time.monotonic() + ROUND_SECONDS
    try:
        report["cases"] = execute(image, prefix)
        report["passed"] = len(report["cases"]) == 6 and all(
            case["passed"] for case in report["cases"]
        )
    except (Exception, KeyboardInterrupt) as error:  # noqa: BLE001 - fail closed and clean up
        report["error"] = (
            error.code if isinstance(error, SmokeFailure) else "SMOKE_FAILED"
        )
    finally:
        _deadline = None
        try:
            report["cleanup_confirmed"] = bool(cleanup(prefix))
        except (Exception, KeyboardInterrupt):  # noqa: BLE001 - never hide unconfirmed cleanup
            report["cleanup_confirmed"] = False
        report["passed"] = report["passed"] and report["cleanup_confirmed"]
    return report


def require_clean_slot():
    # Recover safely even if SIGKILL/OOM prevented the previous controller's finally.
    for args in (
        ["ps", "--all", "--filter", "label=" + LABEL, "--format", "{{.ID}}"],
        ["volume", "ls", "--filter", "label=" + LABEL, "--format", "{{.Name}}"],
    ):
        if control(args).strip():
            raise SmokeFailure("SLOT_HAS_UNCLEAN_RESOURCES")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    parser.add_argument("--source-sha", required=True)
    args = parser.parse_args()
    if sys.platform != "linux":
        parser.error("Real smoke requires a Linux Podman host")
    import fcntl

    # A failed cleanup quarantines the only test slot across subsequent invocations.
    blocked = "/run/astra-course-smoke.blocked"
    with open("/run/astra-course-smoke.lock", "a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if os.path.exists(blocked):
                raise SmokeFailure("SLOT_QUARANTINED")
            require_clean_slot()
            signal.signal(
                signal.SIGTERM,
                lambda *unused: (_ for _ in ()).throw(KeyboardInterrupt()),
            )
            report = run_smoke(args.image, args.source_sha)
            if not report["cleanup_confirmed"]:
                with open(blocked, "w") as quarantine:
                    quarantine.write(report["resource_prefix"] + "\n")
            print(json.dumps(report, sort_keys=True))
            return 0 if report["passed"] else 1
        except (ValueError, OSError) as error:
            code = (
                error.code if isinstance(error, SmokeFailure) else "SMOKE_UNAVAILABLE"
            )
            print(json.dumps({"passed": False, "error": code}))
            return 2


if __name__ == "__main__":
    sys.exit(main())

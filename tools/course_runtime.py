"""Podman execution mechanics. Called only by the authenticated, locked controller."""

import base64
import json
import os
from contextlib import contextmanager
from pathlib import Path

import course_container_smoke as container
from course_executor import cpu_exceeded, diagnose, execute_safely


def prefix(identity):
    # Full identity is journaled; 128-bit names are scoped to this private single-slot service.
    return "astra-course-" + identity[:32]


@contextmanager
def engine():
    original = container.bounded_process

    def bounded(args, *a, **kw):
        if args and args[0] == "podman" and "--cgroup-manager=cgroupfs" not in args:
            args = [args[0], "--cgroup-manager=cgroupfs"] + args[1:]
        return original(args, *a, **kw)

    container.bounded_process = bounded
    try:
        yield
    finally:
        container.bounded_process = original


def accounting_name(identity):
    if len(identity) != 64 or any(c not in "0123456789abcdef" for c in identity):
        raise ValueError("INVALID_ACCOUNTING_ID")
    return "astra-exec-" + identity


def cpu_root():
    root = Path("/sys/fs/cgroup/cpu,cpuacct")
    if not root.is_dir():
        root = Path("/sys/fs/cgroup/cpuacct")
    if not (root / "cpuacct.usage").is_file():
        raise ValueError("CPU_ACCOUNTING_UNAVAILABLE")
    return root


def cleanup_accounting(identity):
    name = accounting_name(identity)
    seen = set()
    for mount in Path("/sys/fs/cgroup").iterdir():
        group = mount / name
        if not group.is_dir():
            continue
        resolved = str(group.resolve())
        if resolved in seen:
            continue
        seen.add(resolved)
        for here, dirs, files in os.walk(str(group), topdown=False):
            if (
                Path(here).is_symlink()
                or "tasks" not in files
                or (Path(here) / "tasks").read_text().strip()
            ):
                return False
            os.rmdir(here)
    return True


def cleanup(identity):
    with engine():
        if not container.cleanup_resources(prefix(identity)):
            return False
        return cleanup_accounting(identity)


def run_args(request, volume):
    args = container.restricted_args(
        request.image, prefix(request.execution_id) + "-run", volume, "run", request.language
    )
    args[-1:-1] = [
        "--cgroups=no-conmon",
        "--cgroup-parent=/" + accounting_name(request.execution_id),
    ]
    return args


def execute(request):
    with engine():
        return execute_safely(request, _execute, cleanup)


def _execute(request):
    name = prefix(request.execution_id)
    volume = name + "-work"
    image = request.image
    language = request.language
    container.control(
        [
            "volume",
            "create",
            "--label=" + container.LABEL + "=" + name,
            "--opt=type=tmpfs",
            "--opt=device=tmpfs",
            "--opt=o=size=33554432,uid=65534,gid=65534,mode=0700,nodev,nosuid",
            volume,
        ]
    )
    container.verify_volume(json.loads(container.control(["volume", "inspect", volume]))[0])
    container.control(
        container.restricted_args(image, name + "-hold", volume, "run", language)[1:]
        + ["/usr/bin/sleep", "360"]
    )
    container.control(["start", name + "-hold"])
    if not container.inspect_container(name + "-hold")["State"].get("Running"):
        raise ValueError("WORK_VOLUME_NOT_HELD")
    compile_cmd = (
        "cat > /work/main.cpp && exec /usr/bin/g++ -std=c++17 -O0 /work/main.cpp -o /work/main"
        if language == "cpp17"
        else "cat > /work/main.py && exec /usr/bin/python3 -m py_compile /work/main.py"
    )
    compile_name = name + "-compile"
    container.control(
        container.restricted_args(image, compile_name, volume, "compile", language)[1:]
        + ["/bin/sh", "-c", compile_cmd]
    )
    container.verify_inspection(
        container.inspect_container(compile_name), "compile", language, volume
    )
    compiled = container.bounded_process(
        ["podman", "start", "--attach", "--interactive", "--sig-proxy=false", compile_name],
        request.code,
        20,
    )
    state = container.inspect_container(compile_name)["State"]
    if compiled.timed_out or compiled.overflow:
        return {"phase": "COMPILE", "diagnosis": "SE", "failure_code": "COMPILE_RESOURCE_FAILURE"}
    exit_code = container.completed_exit(compiled, state)
    diagnosis = diagnose("compile", exit_code, False, False, state.get("OOMKilled", False), None)
    if diagnosis is not None:
        return {
            "phase": "COMPILE",
            "diagnosis": diagnosis,
            "exit_code": exit_code,
            "cpu_ms": None,
            "memory_bytes": None,
        }
    run_name = name + "-run"
    command = ["/work/main"] if language == "cpp17" else ["/usr/bin/python3", "/work/main.py"]
    group = cpu_root() / accounting_name(request.execution_id)
    group.mkdir(mode=0o700)
    container.control(run_args(request, volume)[1:] + command)
    container.verify_inspection(container.inspect_container(run_name), "run", language, volume)
    result = container.bounded_process(
        ["podman", "start", "--attach", "--interactive", "--sig-proxy=false", run_name],
        request.stdin,
        5 if language == "cpp17" else 10,
    )
    state = container.inspect_container(run_name)["State"]
    if not state.get("StartedAt") or state["StartedAt"].startswith("0001-"):
        raise ValueError("CONTAINER_NOT_STARTED")
    code = state.get("ExitCode") if not state.get("Running") else None
    if not result.timed_out and not result.overflow:
        code = container.completed_exit(result, state)
    cpu_ns = int((group / "cpuacct.usage").read_text().strip())
    exceeded = cpu_exceeded(cpu_ns, 2000 if language == "cpp17" else 4000)
    diagnosis = diagnose(
        "run", code, result.timed_out, result.overflow, state.get("OOMKilled", False), exceeded
    )
    value = {
        "phase": "RUN",
        "diagnosis": diagnosis,
        "exit_code": code,
        "cpu_ms": (cpu_ns + 999999) // 1000000,
        "memory_bytes": None,
    }
    if diagnosis is None:
        value["stdout"] = base64.b64encode(result.stdout).decode()
    return value

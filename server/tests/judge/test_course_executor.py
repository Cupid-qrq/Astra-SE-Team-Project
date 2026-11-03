import base64
import json

import pytest

from app.shared.judge import ExecutionError

IMAGE = "sha256:" + "c" * 64


def test_secure_ssh_command_never_places_private_program_on_command_line():
    from app.adapters.course_executor import CourseExecutor, ExecutionResult

    observed = []

    def transport(command, payload, timeout):
        observed.append((command, payload, timeout))
        return json.dumps(
            {
                "phase": "RUN",
                "diagnosis": None,
                "exit_code": 0,
                "stdout": "Mw==",
                "cpu_ms": 20,
                "memory_bytes": None,
                "cleanup_confirmed": True,
            }
        ).encode()

    service = CourseExecutor("oldali", IMAGE, transport=transport)
    value = service.execute("a" * 64, "python3", b"SECRET_CODE", b"SECRET_INPUT")
    assert isinstance(value, ExecutionResult) and value.stdout == b"3"
    command, payload, _ = observed[0]
    assert "SECRET" not in str(command)
    assert "StrictHostKeyChecking=yes" in command and "BatchMode=yes" in command
    assert json.loads(payload)["code"] == base64.b64encode(b"SECRET_CODE").decode()
    assert "SECRET" not in repr(value)


@pytest.mark.parametrize(
    "patch_value",
    [
        {"cleanup_confirmed": False},
        {"diagnosis": "AC"},
        {"cpu_ms": True},
        {"stdout": "%%%"},
        {"exit_code": 1},
        {"phase": "UNKNOWN"},
    ],
)
def test_invalid_or_unclean_results_are_rejected(patch_value):
    from app.adapters.course_executor import CourseExecutor

    value = {
        "phase": "RUN",
        "diagnosis": None,
        "exit_code": 0,
        "stdout": "Mw==",
        "cpu_ms": None,
        "memory_bytes": None,
        "cleanup_confirmed": True,
    } | patch_value
    service = CourseExecutor("oldali", IMAGE, transport=lambda *a: json.dumps(value).encode())
    with pytest.raises(ExecutionError):
        service.execute("a" * 64, "cpp17", b"public", b"")


def test_transport_errors_are_sanitized_without_exception_chain():
    from app.adapters.course_executor import CourseExecutor

    def fail(*args):
        raise RuntimeError("SECRET_TRANSPORT")

    with pytest.raises(ExecutionError) as result:
        CourseExecutor("oldali", IMAGE, transport=fail).execute("a" * 64, "cpp17", b"public", b"")
    assert "SECRET" not in str(result.value)
    assert result.value.__context__ is None and result.value.__cause__ is None


def test_cancel_only_accepts_confirmed_cancelled_identity():
    from app.adapters.course_executor import CourseExecutor

    assert CourseExecutor(
        "oldali", IMAGE, transport=lambda *a: b'{"state":"CANCELLED","cleanup_confirmed":true}'
    ).cancel("a" * 64)
    assert not CourseExecutor(
        "oldali", IMAGE, transport=lambda *a: b'{"cleanup_confirmed":true}'
    ).cancel("a" * 64)


def test_remaining_round_budget_is_sent_to_remote_controller():
    from app.adapters.course_executor import CourseExecutor

    requests = []

    def transport(command, payload, timeout):
        requests.append((json.loads(payload), timeout))
        return (
            b'{"phase":"RUN","diagnosis":null,"exit_code":0,"stdout":"","cleanup_confirmed":true}'
        )

    CourseExecutor("oldali", IMAGE, transport=transport).execute(
        "a" * 64, "python3", b"pass", b"", timeout=1.2
    )
    assert requests[0][0]["timeout_ms"] == 1200

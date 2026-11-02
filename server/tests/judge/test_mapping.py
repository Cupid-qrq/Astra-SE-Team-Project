import base64

import pytest

from app.adapters.judge_mapping import map_observation


def observation(status=3, **kw):
    return map_observation({"status": {"id": status}, "exit_code": 0, **kw})


def test_raw_output_and_missing_metrics_are_preserved():
    raw = b"\xff\x00\r\n"
    value = observation(stdout=base64.b64encode(raw).decode() + "\n", time="0.0001", memory=2)
    assert value.stdout == raw and value.cpu_ms == 1 and value.memory_bytes == 2048
    assert value.diagnosis is None and value.phase == "RUN"
    assert observation(4).diagnosis is None  # backend WA is not product WA
    assert observation().memory_bytes is None and observation().cpu_ms is None


@pytest.mark.parametrize(
    "status,state,phase,diagnosis",
    [
        (1, "QUEUED", "QUEUED", None),
        (2, "PROCESSING", "PROCESSING", None),
        (5, "FINISHED", "UNKNOWN", "TLE"),
        (6, "FINISHED", "COMPILE", "CE"),
        (7, "FINISHED", "RUN", "RE"),
        (8, "FINISHED", "RUN", "RE"),
        (9, "FINISHED", "RUN", "RE"),
        (10, "FINISHED", "RUN", "RE"),
        (11, "FINISHED", "RUN", "RE"),
        (12, "FINISHED", "UNKNOWN", "SE"),
        (13, "FINISHED", "UNKNOWN", "SE"),
        (14, "FINISHED", "UNKNOWN", "SE"),
        (999, "FINISHED", "UNKNOWN", "SE"),
    ],
)
def test_only_explicit_status_evidence_maps_verdict(status, state, phase, diagnosis):
    value = observation(status)
    assert (value.state, value.phase, value.diagnosis) == (state, phase, diagnosis)


def test_python_syntax_error_text_does_not_override_run_phase():
    value = observation(11, exit_code=1, stderr=base64.b64encode(b"SyntaxError: PRIVATE").decode())
    assert value.diagnosis == "RE" and value.phase == "RUN"
    assert "PRIVATE" not in repr(value)
    assert observation(3, exit_code=None).diagnosis == "SE"
    assert observation(3, exit_code=1).diagnosis == "RE"


@pytest.mark.parametrize(
    "patch",
    [
        {"time": "NaN"},
        {"time": "1e1000000"},
        {"time": True},
        {"time": -1},
        {"memory": True},
        {"memory": -1},
        {"memory": 1.5},
        {"exit_code": True},
        {"stdout": "not base64!"},
        {"stdout": False},
        {"status": {"id": True}},
        {"stdout": base64.b64encode(b"x" * (1048576 + 1)).decode()},
    ],
)
def test_bad_payload_is_safe_platform_error(patch):
    value = observation(**patch)
    assert value.diagnosis == "SE" and value.failure_code == "INVALID_BACKEND_RESPONSE"
    assert value.stdout is None

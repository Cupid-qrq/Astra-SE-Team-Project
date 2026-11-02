"""Candidate Judge0 CE mapping v1; runtime units must still be measured in S5."""

import base64
import binascii
from decimal import ROUND_CEILING, Decimal, InvalidOperation
from typing import Any, TypedDict

from app.shared.judge import CaseObservation


class _Fields(TypedDict):
    backend_status: int
    exit_code: int | None
    stdout: bytes | None
    stderr: bytes | None
    compile_output: bytes | None
    cpu_ms: int | None
    memory_bytes: int | None


def platform_error(code: str = "BACKEND_FAILURE") -> CaseObservation:
    return CaseObservation("FINISHED", "UNKNOWN", None, diagnosis="SE", failure_code=code)


def _metric(value: Any, multiplier: int, *, integer: bool = False) -> int | None:
    if value is None:
        return None
    if type(value) not in (int, float, str):
        raise ValueError
    number = Decimal(str(value))
    if not number.is_finite() or number < 0 or number > Decimal(2**63 - 1) / multiplier:
        raise ValueError
    if integer and number != number.to_integral_value():
        raise ValueError
    return int((number * multiplier).to_integral_value(rounding=ROUND_CEILING))


def _output(value: Any) -> bytes | None:
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > 1500000:
        raise ValueError
    # Judge0 CE's Base64.encode64 may wrap lines; only CR/LF are encoding whitespace.
    value = value.replace("\r", "").replace("\n", "")
    raw = base64.b64decode(value, validate=True)
    if len(raw) > 1048576 or base64.b64encode(raw).decode() != value:
        raise ValueError
    return raw


def map_observation(value: Any) -> CaseObservation:
    try:
        status = value["status"]["id"]
        if type(status) is not int:
            raise ValueError
        code = value.get("exit_code")
        if code is not None and (type(code) is not int or not 0 <= code <= 255):
            raise ValueError
        fields: _Fields = dict(
            backend_status=status,
            exit_code=code,
            stdout=_output(value.get("stdout")),
            stderr=_output(value.get("stderr")),
            compile_output=_output(value.get("compile_output")),
            cpu_ms=_metric(value.get("time"), 1000),
            memory_bytes=_metric(value.get("memory"), 1024, integer=True),
        )
        if status in (1, 2):
            return CaseObservation(
                "QUEUED" if status == 1 else "PROCESSING",
                "QUEUED" if status == 1 else "PROCESSING",
                **fields,
            )
        if status == 6:
            return CaseObservation("FINISHED", "COMPILE", diagnosis="CE", **fields)
        if status == 5:
            return CaseObservation(
                "FINISHED",
                "UNKNOWN",
                diagnosis="TLE",
                resource_reason="BACKEND_TIME_LIMIT",
                **fields,
            )
        if status in (7, 8, 9, 10, 11):
            return CaseObservation(
                "FINISHED",
                "RUN",
                diagnosis="RE",
                resource_reason="FILE_LIMIT" if status == 8 else None,
                **fields,
            )
        if status in (3, 4) and code is not None:
            return CaseObservation(
                "FINISHED", "RUN", diagnosis=None if code == 0 else "RE", **fields
            )
        return platform_error()
    except (ValueError, TypeError, KeyError, AttributeError, InvalidOperation, binascii.Error):
        return platform_error("INVALID_BACKEND_RESPONSE")

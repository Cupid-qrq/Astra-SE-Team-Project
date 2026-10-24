"""Pure identity rules. No database, environment or wall-clock access."""

from datetime import UTC, datetime, timedelta
from typing import Any


class Fault(Exception):
    def __init__(
        self,
        status: int,
        code: str,
        message: str,
        *,
        retry: int | None = None,
        commit: bool = False,
        fields: list[dict[str, str]] | None = None,
    ):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message
        self.retry, self.commit, self.fields = retry, commit, fields or []


def require(condition: bool, code: str, message: str, status: int = 409) -> None:
    if not condition:
        raise Fault(status, code, message)


def revision(record: dict[str, Any], expected: int) -> None:
    require(record["revision"] == expected, "REVISION_CONFLICT", "内容已被修改，请重新载入后核对。")


def live_session(session: dict[str, Any], now: datetime) -> bool:
    return (
        session["revoked_at"] is None
        and now < session["expires_at"]
        and now < session["last_seen_at"] + timedelta(minutes=15)
    )


def role(user: dict[str, Any], allowed: tuple[str, ...]) -> None:
    require(user["role"] in allowed, "FORBIDDEN", "当前身份无权执行此操作。", 403)


def utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def byte_limit(value: str, maximum: int, field: str) -> None:
    try:
        valid = len(value.encode("utf-8")) <= maximum
    except UnicodeEncodeError:
        valid = False
    require(valid, "VALIDATION_ERROR", f"{field}超出UTF-8字节上限或包含无效字符。", 422)

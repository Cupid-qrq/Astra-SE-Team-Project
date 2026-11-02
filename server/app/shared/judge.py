"""Internal execution port. No network, database, environment or local execution."""

import hashlib
import json
from dataclasses import dataclass, field
from typing import Literal, Protocol
from uuid import UUID

LanguageKey = Literal["cpp17", "python3"]
Phase = Literal["QUEUED", "PROCESSING", "COMPILE", "RUN", "UNKNOWN"]
Diagnosis = Literal["CE", "RE", "TLE", "SE"]


class ExecutionError(ValueError):
    """Only constant error codes, never rejected values or transport exceptions."""


def uuid_value(value: str) -> str:
    try:
        parsed = UUID(value)
        if parsed.int == 0:
            raise ValueError
        return str(parsed)
    except (ValueError, TypeError, AttributeError):
        pass
    raise ExecutionError("INVALID_EXECUTION_ID")


def sha_value(value: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(c not in "0123456789abcdef" for c in value)
    ):
        raise ExecutionError("INVALID_EXECUTION_DIGEST")
    return value


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode()
    ).hexdigest()


@dataclass(frozen=True)
class CaseLease:
    attempt_id: str
    generation: int
    lease_epoch: int
    testcase_order: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "attempt_id", uuid_value(self.attempt_id))
        if (
            any(
                type(v) is not int or v < 1
                for v in (self.generation, self.lease_epoch, self.testcase_order)
            )
            or self.testcase_order > 10
        ):
            raise ExecutionError("INVALID_EXECUTION_LEASE")

    @property
    def key(self) -> str:
        return digest([self.attempt_id, self.generation, self.lease_epoch, self.testcase_order])


@dataclass(frozen=True)
class ExecutionIdentity:
    lease: CaseLease
    request_hash: str
    profile_hash: str

    def __post_init__(self) -> None:
        sha_value(self.request_hash)
        sha_value(self.profile_hash)

    @property
    def execution_key(self) -> str:
        return self.lease.key

    def wire(self) -> dict[str, object]:
        return dict(
            attempt_id=self.lease.attempt_id,
            generation=self.lease.generation,
            lease_epoch=self.lease.lease_epoch,
            testcase_order=self.lease.testcase_order,
            execution_key=self.execution_key,
            request_hash=self.request_hash,
            profile_hash=self.profile_hash,
        )


@dataclass(frozen=True)
class CaseRequest:
    lease: CaseLease
    profile_id: str
    profile_hash: str
    language_key: LanguageKey
    code: bytes = field(repr=False)
    stdin: bytes = field(repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "profile_id", uuid_value(self.profile_id))
        sha_value(self.profile_hash)
        if self.language_key not in ("cpp17", "python3"):
            raise ExecutionError("INVALID_EXECUTION_LANGUAGE")
        if (
            type(self.code) is not bytes
            or type(self.stdin) is not bytes
            or not 1 <= len(self.code) <= 65536
            or len(self.stdin) > 65536
        ):
            raise ExecutionError("INVALID_EXECUTION_INPUT")
        try:
            self.code.decode("utf-8")
            self.stdin.decode("utf-8")
        except UnicodeError:
            pass
        else:
            return
        # Raise after leaving the handler: `from None` alone retains __context__.
        raise ExecutionError("INVALID_EXECUTION_UTF8")

    @property
    def identity(self) -> ExecutionIdentity:
        value = [
            self.profile_id,
            self.profile_hash,
            self.language_key,
            hashlib.sha256(self.code).hexdigest(),
            hashlib.sha256(self.stdin).hexdigest(),
        ]
        return ExecutionIdentity(self.lease, digest(value), self.profile_hash)


@dataclass(frozen=True)
class Ticket:
    identity: ExecutionIdentity
    backend_token: str = field(repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "backend_token", uuid_value(self.backend_token))


@dataclass(frozen=True)
class CreateOutcome:
    state: Literal["CREATED", "CREATE_UNKNOWN", "REJECTED"]
    identity: ExecutionIdentity
    ticket: Ticket | None = field(default=None, repr=False)
    reason: str | None = None


@dataclass(frozen=True)
class CaseObservation:
    state: Literal["QUEUED", "PROCESSING", "FINISHED"]
    phase: Phase
    backend_status: int | None
    exit_code: int | None = None
    stdout: bytes | None = field(default=None, repr=False)
    stderr: bytes | None = field(default=None, repr=False)
    compile_output: bytes | None = field(default=None, repr=False)
    cpu_ms: int | None = None
    memory_bytes: int | None = None
    diagnosis: Diagnosis | None = None
    resource_reason: str | None = None
    failure_code: str | None = None

    def __post_init__(self) -> None:
        for value in (self.cpu_ms, self.memory_bytes):
            if value is not None and (type(value) is not int or value < 0):
                raise ExecutionError("INVALID_EXECUTION_METRIC")


@dataclass(frozen=True)
class CleanupOutcome:
    confirmed: bool
    proof_id: str | None = None
    reason: str | None = None


class JudgePort(Protocol):
    def create_case(self, request: CaseRequest) -> CreateOutcome: ...
    def poll_case(self, ticket: Ticket) -> CaseObservation: ...
    def cancel_and_cleanup(
        self, identity: ExecutionIdentity, ticket: Ticket | None = None
    ) -> CleanupOutcome: ...

"""HTTPS-only candidate adapter. No local execution, retries or production wiring."""

import base64
import ipaddress
import json
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from time import monotonic
from typing import Any, Self
from urllib.parse import urlsplit

import httpx

from app.adapters.judge_mapping import map_observation, platform_error
from app.adapters.judge_profiles import ProfileCatalog
from app.shared.judge import (
    CaseObservation,
    CaseRequest,
    CleanupOutcome,
    CreateOutcome,
    ExecutionError,
    ExecutionIdentity,
    Ticket,
    uuid_value,
)

MAX_RESPONSE = 6 * 1024 * 1024
_sensitive: ContextVar[bool] = ContextVar("astra_judge_sensitive_transport", default=False)


class _TransportFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return not _sensitive.get()


@contextmanager
def sensitive_transport() -> Iterator[None]:
    """Suppress HTTPX URL and httpcore header traces only in this execution context."""
    for name in (
        "httpx",
        "httpcore.connection",
        "httpcore.http11",
        "httpcore.http2",
        "httpcore.proxy",
        "httpcore.socks",
    ):
        logger = logging.getLogger(name)
        if not any(isinstance(f, _TransportFilter) for f in logger.filters):
            logger.addFilter(_TransportFilter())
    token = _sensitive.set(True)
    try:
        yield
    finally:
        _sensitive.reset(token)


def https_origin(value: str) -> str:
    try:
        url = urlsplit(value)
        host = url.hostname
        if (
            url.scheme != "https"
            or not host
            or url.username
            or url.password
            or url.path not in ("", "/")
            or url.query
            or url.fragment
            or any(c.isspace() or ord(c) < 33 or ord(c) > 126 for c in value)
            or "\\" in value
            or url.port == 0
        ):
            raise ValueError
        if (
            host == "localhost"
            or host.endswith(".localhost")
            or host in ("ce.judge0.com", "extra-ce.judge0.com")
            or host.endswith(".rapidapi.com")
        ):
            raise ValueError
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            address = None
        if address is not None and (
            address.is_loopback
            or address.is_link_local
            or address.is_unspecified
            or address.is_multicast
        ):
            raise ValueError
        return value.rstrip("/")
    except (ValueError, TypeError, AttributeError):
        raise ExecutionError("INVALID_JUDGE_ORIGIN") from None


@dataclass(frozen=True)
class Judge0Target:
    management_origin: str
    supervisor_origin: str
    deployment_id: str
    auth_token: str = field(repr=False)
    supervisor_token: str = field(repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "management_origin", https_origin(self.management_origin))
        object.__setattr__(self, "supervisor_origin", https_origin(self.supervisor_origin))
        object.__setattr__(self, "deployment_id", uuid_value(self.deployment_id))
        if any(
            not isinstance(v, str)
            or len(v) < 32
            or len(v) > 4096
            or any(ord(c) < 33 or ord(c) > 126 for c in v)
            for v in (self.auth_token, self.supervisor_token)
        ):
            raise ExecutionError("INVALID_JUDGE_CREDENTIALS")


def strict_json(raw: bytes) -> Any:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for k, v in items:
            if k in result:
                raise ValueError
            result[k] = v
        return result

    def reject(value: str) -> Any:
        raise ValueError

    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=reject)
    except (ValueError, UnicodeError, RecursionError):
        raise ExecutionError("INVALID_BACKEND_RESPONSE") from None


def read_json(
    client: httpx.Client,
    method: str,
    url: str,
    *,
    headers: dict[str, str],
    payload: dict[str, Any] | None = None,
) -> tuple[int, Any]:
    deadline = monotonic() + 10.0
    with sensitive_transport():
        with client.stream(
            method, url, headers={**headers, "Accept-Encoding": "identity"}, json=payload
        ) as response:
            if monotonic() > deadline:
                raise ExecutionError("BACKEND_DEADLINE")
            if response.headers.get("content-encoding", "identity").lower() != "identity":
                raise ExecutionError("INVALID_BACKEND_RESPONSE")
            data = bytearray()
            for chunk in response.iter_bytes():
                if monotonic() > deadline or len(chunk) > MAX_RESPONSE - len(data):
                    raise ExecutionError("BACKEND_DEADLINE_OR_SIZE")
                data.extend(chunk)
                if len(data) > MAX_RESPONSE:
                    raise ExecutionError("INVALID_BACKEND_RESPONSE")
            # Definite HTTP rejection needs no body parsing, and never echoes its content.
            if response.status_code not in (200, 201):
                return response.status_code, None
            return response.status_code, strict_json(bytes(data))


class Judge0Adapter:
    def __init__(
        self,
        target: Judge0Target,
        catalog: ProfileCatalog,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.target = target
        self.catalog = catalog
        self.client = httpx.Client(
            verify=True,
            trust_env=False,
            follow_redirects=False,
            timeout=httpx.Timeout(5.0),
            limits=httpx.Limits(max_connections=4, max_keepalive_connections=4),
            transport=transport
            if transport is not None
            else httpx.HTTPTransport(
                verify=True,
                trust_env=False,
                retries=0,
                limits=httpx.Limits(max_connections=4, max_keepalive_connections=4),
            ),
        )

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        self.client.close()

    def create_case(self, request: CaseRequest) -> CreateOutcome:
        identity = request.identity
        try:
            profile = self.catalog.require(
                request.profile_id, request.profile_hash, request.language_key
            )
            language = profile.language(request.language_key)
        except ExecutionError:
            return CreateOutcome("REJECTED", identity, reason="PROFILE_NOT_ALLOWED")
        payload = dict(
            source_code=base64.b64encode(request.code).decode(),
            stdin=base64.b64encode(request.stdin).decode(),
            language_id=language.language_id,
            cpu_time_limit=language.cpu_ms / 1000,
            wall_time_limit=language.wall_ms / 1000,
            cpu_extra_time=0,
            memory_limit=262144,
            max_file_size=1024,
            max_processes_and_or_threads=1,
            enable_network=False,
            number_of_runs=1,
            enable_per_process_and_thread_time_limit=False,
            enable_per_process_and_thread_memory_limit=False,
        )
        headers = {
            "X-Auth-Token": self.target.auth_token,
            "X-Astra-Deployment-Id": self.target.deployment_id,
            **{"X-Astra-" + k.replace("_", "-"): str(v) for k, v in identity.wire().items()},
        }
        try:
            status, data = read_json(
                self.client,
                "POST",
                self.target.management_origin + "/submissions?base64_encoded=true&wait=false",
                headers=headers,
                payload=payload,
            )
            if status in (401, 403, 422):
                return CreateOutcome("REJECTED", identity, reason="BACKEND_REJECTED")
            if status == 201 and isinstance(data, dict) and set(data) == {"token"}:
                return CreateOutcome("CREATED", identity, Ticket(identity, data["token"]))
        except (httpx.HTTPError, ExecutionError):
            pass
        return CreateOutcome("CREATE_UNKNOWN", identity, reason="CREATE_NOT_CONFIRMED")

    def poll_case(self, ticket: Ticket) -> CaseObservation:
        fields = "status,exit_code,stdout,stderr,compile_output,time,memory"
        try:
            status, data = read_json(
                self.client,
                "GET",
                self.target.management_origin
                + f"/submissions/{ticket.backend_token}?base64_encoded=true&fields={fields}",
                headers={"X-Auth-Token": self.target.auth_token},
            )
            if status == 200:
                return map_observation(data)
        except (httpx.HTTPError, ExecutionError):
            pass
        return platform_error()

    def cancel_and_cleanup(
        self, identity: ExecutionIdentity, ticket: Ticket | None = None
    ) -> CleanupOutcome:
        if ticket is not None and ticket.identity != identity:
            return CleanupOutcome(False, reason="TICKET_IDENTITY_MISMATCH")
        try:
            status, data = read_json(
                self.client,
                "POST",
                self.target.supervisor_origin
                + f"/v1/executions/{identity.execution_key}/cancel-and-cleanup",
                headers={"Authorization": "Bearer " + self.target.supervisor_token},
                payload={
                    "identity": identity.wire(),
                    "backend_token": ticket.backend_token if ticket else None,
                },
            )
            if (
                status == 200
                and isinstance(data, dict)
                and set(data)
                == {
                    "protocol",
                    "deployment_id",
                    "identity",
                    "proof_id",
                    "stopped",
                    "directory_cleaned",
                    "creation_resolved",
                    "fenced_epoch",
                }
                and data["protocol"] == "astra-supervisor-v1"
                and data["deployment_id"] == self.target.deployment_id
                and isinstance(data["identity"], dict)
                and all(
                    type(data["identity"].get(k)) is int
                    for k in ("generation", "lease_epoch", "testcase_order")
                )
                and data["identity"] == identity.wire()
                and all(
                    data[k] is True for k in ("stopped", "directory_cleaned", "creation_resolved")
                )
                and type(data["fenced_epoch"]) is int
                and data["fenced_epoch"] == identity.lease.lease_epoch
            ):
                return CleanupOutcome(True, uuid_value(data["proof_id"]))
        except (httpx.HTTPError, ExecutionError):
            pass
        return CleanupOutcome(False, reason="CLEANUP_UNCONFIRMED")

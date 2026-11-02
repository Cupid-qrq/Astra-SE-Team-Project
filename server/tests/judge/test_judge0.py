import base64
import json
import logging
from dataclasses import replace

import httpx
import pytest

from app.adapters.judge0 import Judge0Adapter, Judge0Target
from app.adapters.judge_profiles import ProfileCatalog, RuntimeProfile
from app.shared.judge import CaseLease, CaseRequest, ExecutionError, Ticket

TOKEN = "90000000-0000-4000-8000-000000000001"
DEPLOYMENT = "30000000-0000-4000-8000-000000000001"


@pytest.fixture
def target():
    return Judge0Target(
        "https://judge.internal",
        "https://supervisor.internal",
        DEPLOYMENT,
        "AUTH_SECRET_1234567890123456789012",
        "SUP_SECRET_12345678901234567890123",
    )


@pytest.fixture
def request_case(snapshot, language_ids):
    profile = RuntimeProfile.from_public(snapshot, language_ids)
    return CaseRequest(
        CaseLease("10000000-0000-4000-8000-000000000001", 1, 1, 1),
        profile.profile_id,
        profile.profile_hash,
        "python3",
        b"PRIVATE_SOURCE\x00",
        b"PRIVATE_STDIN",
    )


def adapter(target, snapshot, language_ids, handler):
    return Judge0Adapter(
        target,
        ProfileCatalog([RuntimeProfile.from_public(snapshot, language_ids)]),
        transport=httpx.MockTransport(handler),
    )


def test_create_has_fixed_target_explicit_mapping_and_one_post(
    target, snapshot, language_ids, request_case
):
    calls = []

    def handle(req):
        calls.append(req)
        body = json.loads(req.content)
        assert req.url.host == "judge.internal" and req.url.path == "/submissions"
        assert req.url.params["wait"] == "false" and req.url.params["base64_encoded"] == "true"
        assert req.headers["X-Auth-Token"] == target.auth_token
        assert req.headers["X-Astra-Execution-Key"] == request_case.identity.execution_key
        assert req.headers["X-Astra-Request-Hash"] == request_case.identity.request_hash
        assert body["language_id"] == 733
        assert base64.b64decode(body["source_code"]) == request_case.code
        assert base64.b64decode(body["stdin"]) == request_case.stdin
        assert body["cpu_time_limit"] == 4 and body["wall_time_limit"] == 10
        assert body["memory_limit"] == 262144 and body["max_file_size"] == 1024
        assert body["max_processes_and_or_threads"] == 1
        assert body["enable_network"] is False and body["cpu_extra_time"] == 0
        assert body["enable_per_process_and_thread_memory_limit"] is False
        assert body["enable_per_process_and_thread_time_limit"] is False
        assert body["number_of_runs"] == 1
        assert set(body) == {
            "source_code",
            "stdin",
            "language_id",
            "cpu_time_limit",
            "wall_time_limit",
            "cpu_extra_time",
            "memory_limit",
            "max_file_size",
            "max_processes_and_or_threads",
            "enable_network",
            "enable_per_process_and_thread_memory_limit",
            "enable_per_process_and_thread_time_limit",
            "number_of_runs",
        }
        return httpx.Response(201, json={"token": TOKEN})

    with adapter(target, snapshot, language_ids, handle) as port:
        result = port.create_case(request_case)
    assert result.state == "CREATED" and result.ticket.backend_token == TOKEN
    assert len(calls) == 1
    assert "AUTH_SECRET" not in repr(target)


@pytest.mark.parametrize(
    "kind",
    ["timeout", "500", "redirect", "badjson", "badtoken", "oversize", "duplicate", "compressed"],
)
def test_ambiguous_create_never_retries_or_leaks(
    kind, target, snapshot, language_ids, request_case, caplog
):
    calls = []
    caplog.set_level(logging.DEBUG)

    def handle(req):
        calls.append(req)
        logging.getLogger("httpcore.http11").debug("sensitive headers %s", req.headers)
        if kind == "timeout":
            raise httpx.ReadTimeout("PRIVATE_SOURCE", request=req)
        if kind == "500":
            return httpx.Response(500, text="PRIVATE_SOURCE")
        if kind == "redirect":
            return httpx.Response(307, headers={"Location": "https://evil.test"})
        if kind == "badjson":
            return httpx.Response(201, text="PRIVATE_SOURCE")
        if kind == "badtoken":
            return httpx.Response(201, json={"token": "PRIVATE_SOURCE"})
        if kind == "oversize":
            return httpx.Response(201, content=b"x" * (6 * 1024 * 1024 + 1))
        if kind == "duplicate":
            return httpx.Response(201, text='{"token":"' + TOKEN + '","token":"' + TOKEN + '"}')
        return httpx.Response(201, content=b"bad", headers={"Content-Encoding": "gzip"})

    with adapter(target, snapshot, language_ids, handle) as port:
        result = port.create_case(request_case)
    assert result.state == "CREATE_UNKNOWN" and result.ticket is None and len(calls) == 1
    assert all(
        secret not in caplog.text + repr(result)
        for secret in ["AUTH_SECRET", "PRIVATE_SOURCE", TOKEN]
    )


@pytest.mark.parametrize("status", [401, 403, 422])
def test_definite_create_rejection(status, target, snapshot, language_ids, request_case):
    with adapter(
        target,
        snapshot,
        language_ids,
        lambda _: httpx.Response(status, json={"private": "never echo"}),
    ) as port:
        assert port.create_case(request_case).state == "REJECTED"


def test_bad_profile_rejected_before_network(target, snapshot, language_ids, request_case):
    def forbidden(_):
        raise AssertionError("network")

    with adapter(target, snapshot, language_ids, forbidden) as port:
        assert port.create_case(replace(request_case, profile_hash="f" * 64)).state == "REJECTED"


@pytest.mark.parametrize(
    "url",
    [
        "http://judge.internal",
        "https://ce.judge0.com",
        "https://localhost",
        "https://127.0.0.1",
        "https://user:secret@judge.test",
        "https://judge.test/path",
        "https://judge.test?token=secret",
        "https://judge.test#secret",
    ],
)
def test_target_rejects_unsafe_or_ambiguous_origins(url, target):
    with pytest.raises(ExecutionError) as error:
        replace(target, management_origin=url)
    assert "secret" not in str(error.value)


def test_poll_uses_bounded_encoded_fields_and_suppresses_token_log(
    target, snapshot, language_ids, request_case, caplog
):
    caplog.set_level(logging.DEBUG)

    def handle(req):
        assert req.method == "GET" and req.url.path == "/submissions/" + TOKEN
        assert req.url.params["base64_encoded"] == "true"
        assert "source_code" not in req.url.params["fields"]
        return httpx.Response(
            200,
            json={
                "status": {"id": 3},
                "exit_code": 0,
                "stdout": base64.b64encode(b"\xff").decode(),
            },
        )

    with adapter(target, snapshot, language_ids, handle) as port:
        result = port.poll_case(Ticket(request_case.identity, TOKEN))
    assert result.stdout == b"\xff" and result.diagnosis is None
    assert TOKEN not in caplog.text and "AUTH_SECRET" not in caplog.text
    logging.getLogger("httpx").info("unrelated request remains visible")
    assert "unrelated request remains visible" in caplog.text


def proof(request_case):
    return {
        "protocol": "astra-supervisor-v1",
        "deployment_id": DEPLOYMENT,
        "identity": request_case.identity.wire(),
        "proof_id": "40000000-0000-4000-8000-000000000001",
        "stopped": True,
        "directory_cleaned": True,
        "creation_resolved": True,
        "fenced_epoch": 1,
    }


def test_cleanup_requires_supervisor_bound_attestation(
    target, snapshot, language_ids, request_case
):
    calls = []

    def handle(req):
        calls.append(req)
        assert req.method == "POST" and req.url.host == "supervisor.internal"
        assert (
            req.url.path
            == "/v1/executions/" + request_case.identity.execution_key + "/cancel-and-cleanup"
        )
        assert req.headers["Authorization"] == "Bearer " + target.supervisor_token
        assert json.loads(req.content) == {
            "identity": request_case.identity.wire(),
            "backend_token": TOKEN,
        }
        return httpx.Response(200, json=proof(request_case))

    with adapter(target, snapshot, language_ids, handle) as port:
        result = port.cancel_and_cleanup(
            request_case.identity, Ticket(request_case.identity, TOKEN)
        )
    assert result.confirmed and len(calls) == 1


@pytest.mark.parametrize(
    "field,value",
    [
        ("stopped", False),
        ("directory_cleaned", False),
        ("creation_resolved", False),
        ("fenced_epoch", True),
        ("fenced_epoch", 2),
        ("proof_id", "invalid"),
        ("identity", {}),
        ("deployment_id", "30000000-0000-4000-8000-000000000002"),
    ],
)
def test_unconfirmed_cleanup_keeps_slot_quarantined(
    field, value, target, snapshot, language_ids, request_case
):
    evidence = proof(request_case)
    evidence[field] = value
    with adapter(
        target, snapshot, language_ids, lambda _: httpx.Response(200, json=evidence)
    ) as port:
        assert not port.cancel_and_cleanup(request_case.identity).confirmed


def test_mismatched_ticket_never_sent_to_cleanup(target, snapshot, language_ids, request_case):
    def forbidden(_):
        raise AssertionError("network")

    other = replace(request_case, lease=replace(request_case.lease, lease_epoch=2))
    with adapter(target, snapshot, language_ids, forbidden) as port:
        assert not port.cancel_and_cleanup(
            request_case.identity, Ticket(other.identity, TOKEN)
        ).confirmed


def test_cleanup_identity_integer_fields_cannot_be_booleans(
    target, snapshot, language_ids, request_case
):
    evidence = proof(request_case)
    evidence["identity"]["generation"] = True
    with adapter(
        target, snapshot, language_ids, lambda _: httpx.Response(200, json=evidence)
    ) as port:
        assert not port.cancel_and_cleanup(request_case.identity).confirmed


def test_native_transport_ignores_proxy_and_ca_environment(
    target, snapshot, language_ids, monkeypatch
):
    seen = {}

    def transport(**kwargs):
        seen.update(kwargs)
        return httpx.MockTransport(lambda _: httpx.Response(503))

    monkeypatch.setenv("HTTPS_PROXY", "http://untrusted.test:8888")
    monkeypatch.setenv("SSL_CERT_FILE", "invalid-private-ca")
    monkeypatch.setattr(httpx, "HTTPTransport", transport)
    with Judge0Adapter(
        target, ProfileCatalog([RuntimeProfile.from_public(snapshot, language_ids)])
    ):
        pass
    assert seen["verify"] is True and seen["trust_env"] is False and seen["retries"] == 0
    assert seen["limits"].max_connections == 4


def test_drip_response_has_deadline_beyond_per_read_timeout(
    target, snapshot, language_ids, request_case, monkeypatch
):
    ticks = iter([0.0, 0.0, 11.0])
    monkeypatch.setattr("app.adapters.judge0.monotonic", lambda: next(ticks), raising=False)
    chunks = []

    class Drip(httpx.SyncByteStream):
        def __iter__(self):
            chunks.append(1)
            yield b"{"
            chunks.append(2)
            yield b"}"

    with adapter(
        target, snapshot, language_ids, lambda _: httpx.Response(201, stream=Drip())
    ) as port:
        result = port.create_case(request_case)
    assert result.state == "CREATE_UNKNOWN" and chunks == [1]

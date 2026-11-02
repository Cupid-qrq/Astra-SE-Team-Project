from copy import deepcopy
from dataclasses import replace

import pytest

from app.adapters.judge_profiles import ProfileCatalog, RuntimeProfile
from app.modules.problems.domain import profile_digest
from app.shared.judge import CaseLease, CaseObservation, CaseRequest, ExecutionError, Ticket


def lease():
    return CaseLease("10000000-0000-4000-8000-000000000001", 1, 1, 1)


def test_identity_binds_lease_and_exact_payload(snapshot, language_ids):
    profile = RuntimeProfile.from_public(snapshot, language_ids)
    request = CaseRequest(
        lease(),
        profile.profile_id,
        profile.profile_hash,
        "python3",
        b"PRIVATE_CODE\x00",
        b"PRIVATE_INPUT",
    )
    assert request.identity.profile_hash == profile_digest(snapshot)
    assert (
        request.identity.execution_key == replace(request, code=b"different").identity.execution_key
    )
    assert (
        request.identity.request_hash != replace(request, code=b"different").identity.request_hash
    )
    for changed in [
        replace(lease(), generation=2),
        replace(lease(), lease_epoch=2),
        replace(lease(), testcase_order=2),
        replace(lease(), attempt_id="10000000-0000-4000-8000-000000000002"),
    ]:
        assert (
            replace(request, lease=changed).identity.execution_key != request.identity.execution_key
        )
    ticket = Ticket(request.identity, "90000000-0000-4000-8000-000000000001")
    observation = CaseObservation(
        "FINISHED", "RUN", 3, 0, stdout=b"HIDDEN_OUTPUT", stderr=b"HIDDEN_ERROR"
    )
    assert "PRIVATE" not in repr(request)
    assert "90000000" not in repr(ticket)
    assert "HIDDEN" not in repr(observation)
    assert observation.cpu_ms is None and observation.memory_bytes is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("generation", True),
        ("generation", 0),
        ("lease_epoch", -1),
        ("testcase_order", 11),
        ("attempt_id", "secret-invalid-id"),
    ],
)
def test_bad_lease_is_rejected_without_input_echo(field, value):
    with pytest.raises(ExecutionError) as error:
        replace(lease(), **{field: value})
    assert "secret-invalid-id" not in str(error.value)


def test_catalog_freezes_public_snapshot_and_binds_A_digest(snapshot, language_ids):
    profile = RuntimeProfile.from_public(snapshot, language_ids)
    catalog = ProfileCatalog([profile])
    assert catalog.bind(snapshot) is profile
    assert profile.language("cpp17").language_id == 912
    assert profile.profile_hash == profile_digest(snapshot)
    snapshot["languages"][0]["version"] = "changed"
    assert profile.public_snapshot()["languages"][0]["version"] == "fixture-cpp"
    with pytest.raises(ExecutionError):
        catalog.bind(snapshot)
    with pytest.raises(ExecutionError):
        profile.language("java")
    copy = profile.public_snapshot()
    copy["memory_bytes"] = 1
    assert profile.public_snapshot()["memory_bytes"] == 268435456


@pytest.mark.parametrize(
    "field,value",
    [
        ("memory_bytes", 1),
        ("output_bytes", 0),
        ("directory_bytes", 1),
        ("run_entities", True),
        ("compile_timeout_ms", 1),
        ("compile_memory_bytes", 1),
        ("compile_entities", 1),
        ("comparison", "UNICODE"),
    ],
)
def test_resource_tampering_is_rejected(snapshot, language_ids, field, value):
    snapshot[field] = value
    with pytest.raises(ExecutionError):
        RuntimeProfile.from_public(snapshot, language_ids)


@pytest.mark.parametrize(
    "kind",
    [
        "bool_id",
        "missing_id",
        "duplicate_language",
        "unknown_language",
        "bad_digest",
        "bad_cpu",
        "extra_field",
    ],
)
def test_language_mapping_and_unknown_fields_are_rejected(snapshot, language_ids, kind):
    if kind == "bool_id":
        language_ids["cpp17"] = True
    elif kind == "missing_id":
        language_ids.pop("python3")
    elif kind == "duplicate_language":
        snapshot["languages"][1] = deepcopy(snapshot["languages"][0])
    elif kind == "unknown_language":
        snapshot["languages"][0]["language_key"] = "java"
    elif kind == "bad_digest":
        snapshot["languages"][0]["image_digest"] = "latest"
    elif kind == "bad_cpu":
        snapshot["languages"][0]["cpu_time_ms"] = 2001
    else:
        snapshot["override_network"] = True
    with pytest.raises(ExecutionError):
        RuntimeProfile.from_public(snapshot, language_ids)


def test_duplicate_catalog_and_wrong_hash_rejected(snapshot, language_ids):
    profile = RuntimeProfile.from_public(snapshot, language_ids)
    with pytest.raises(ExecutionError):
        ProfileCatalog([profile, profile])
    catalog = ProfileCatalog([profile])
    with pytest.raises(ExecutionError):
        catalog.require(profile.profile_id, "0" * 64, "cpp17")
    with pytest.raises(ExecutionError):
        Ticket(
            CaseRequest(
                lease(), profile.profile_id, profile.profile_hash, "cpp17", b"x", b""
            ).identity,
            "invalid-secret-ticket",
        )

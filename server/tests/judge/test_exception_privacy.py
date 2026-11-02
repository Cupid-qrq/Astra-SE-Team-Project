import pytest

from app.adapters.judge0 import https_origin, strict_json
from app.adapters.judge_inventory import load_inventory
from app.adapters.judge_profiles import ProfileCatalog, RuntimeProfile
from app.shared.judge import CaseLease, CaseRequest, ExecutionError, uuid_value


@pytest.mark.parametrize(
    "kind", ["uuid", "source", "stdin", "json", "profile", "binding", "origin", "registration"]
)
def test_safe_errors_do_not_retain_sensitive_exception_context(
    kind, snapshot, language_ids, tmp_path
):
    profile = RuntimeProfile.from_public(snapshot, language_ids)
    lease = CaseLease("10000000-0000-4000-8000-000000000001", 1, 1, 1)

    def action():
        if kind == "uuid":
            return uuid_value("PRIVATE_TOKEN")
        if kind in ("source", "stdin"):
            return CaseRequest(
                lease,
                profile.profile_id,
                profile.profile_hash,
                "python3",
                b"PRIVATE_SOURCE\xff" if kind == "source" else b"valid",
                b"PRIVATE_INPUT\xff" if kind == "stdin" else b"valid",
            )
        if kind == "json":
            return strict_json(b'{"PRIVATE_HIDDEN":')
        if kind == "profile":
            snapshot["memory_bytes"] = True
            return RuntimeProfile.from_public(snapshot, language_ids)
        if kind == "binding":
            return ProfileCatalog([profile]).bind({"profile_id": "PRIVATE_PROFILE"})
        if kind == "origin":
            return https_origin("https://user:PRIVATE_PASSWORD@judge.internal")
        path = tmp_path / "registration.json"
        path.write_bytes(b'{"PRIVATE_HIDDEN":')
        return load_inventory(path)

    with pytest.raises(ExecutionError) as error:
        action()
    assert "PRIVATE" not in str(error.value)
    assert error.value.__context__ is None
    assert error.value.__cause__ is None

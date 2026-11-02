import hashlib
import json

import httpx
import pytest

from app.adapters.judge_inventory import (
    CAPABILITIES,
    load_inventory,
    probe_inventory,
    verify_evidence,
)
from app.shared.judge import ExecutionError, digest


@pytest.fixture
def manifest(snapshot, language_ids):
    about = {"version": "synthetic-version"}
    languages = [{"id": 733, "name": "synthetic-python"}, {"id": 912, "name": "synthetic-cpp"}]
    config = {"enable_network": False, "allow_enable_network": False}
    return dict(
        schema="astra-judge-registration-v1",
        status="REGISTERED",
        business_vm_id="10000000-0000-4000-8000-000000000001",
        judge_vm_id="20000000-0000-4000-8000-000000000001",
        deployment_id="30000000-0000-4000-8000-000000000001",
        management_origin="https://judge.internal",
        supervisor_origin="https://supervisor.internal",
        auth_env="ASTRA_JUDGE_TOKEN",
        supervisor_auth_env="ASTRA_SUPERVISOR_TOKEN",
        resources={"vcpu": 4, "memory_bytes": 8589934592, "disk_bytes": 64424509440, "slots": 4},
        vm_image="sha256:" + "a" * 64,
        engine_image="sha256:" + "b" * 64,
        os_version="synthetic-linux",
        kernel_version="synthetic-kernel",
        hypervisor="synthetic-hypervisor",
        source_sha="f" * 40,
        mapping_version="astra-judge0-ce-v1",
        profiles=[{"snapshot": snapshot, "language_ids": language_ids}],
        about_hash=digest(about),
        languages_hash=digest(languages),
        config_hash=digest(config),
    )


def registration(tmp_path, manifest):
    path = tmp_path / "deployment.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return load_inventory(path)


def test_registration_is_frozen_but_not_execution_ready(tmp_path, manifest):
    inventory = registration(tmp_path, manifest)
    original = inventory.fingerprint
    manifest["resources"]["slots"] = 99
    assert inventory.fingerprint == original and inventory.resources["slots"] == 4
    assert verify_evidence(inventory, tmp_path) == tuple(
        f"MISSING_OR_INVALID_V-{i:02}" for i in range(1, 7)
    )


@pytest.mark.parametrize(
    "change",
    [
        "unverified",
        "samevm",
        "loopback",
        "demo",
        "resourcebool",
        "smallvm",
        "mapping",
        "extra",
        "secretvalue",
    ],
)
def test_invalid_registration_is_safe_failure(tmp_path, manifest, change):
    if change == "unverified":
        manifest["status"] = "UNVERIFIED"
    if change == "samevm":
        manifest["judge_vm_id"] = manifest["business_vm_id"]
    if change == "loopback":
        manifest["management_origin"] = "https://127.0.0.1"
    if change == "demo":
        manifest["management_origin"] = "https://ce.judge0.com"
    if change == "resourcebool":
        manifest["resources"]["vcpu"] = True
    if change == "smallvm":
        manifest["resources"]["disk_bytes"] = 1
    if change == "mapping":
        manifest["mapping_version"] = "guess"
    if change == "extra":
        manifest["enabled"] = True
    if change == "secretvalue":
        manifest["auth_env"] = "PASSWORD_PRIVATE_VALUE"
    with pytest.raises(ExecutionError) as error:
        registration(tmp_path, manifest)
    assert "PRIVATE" not in str(error.value)


def write_evidence(inventory, root):
    for i in range(1, 7):
        key = f"V-{i:02}"
        raw = root / (key + ".txt")
        raw.write_bytes(b"synthetic aggregate observations")
        record = dict(
            schema="astra-isolation-evidence-v1",
            test_id=key,
            result="PASS",
            synthetic=False,
            fingerprint=inventory.fingerprint,
            source_sha=inventory.source_sha,
            performed_at="2026-11-02T01:00:00Z",
            operator="fixture-B",
            reviewer="fixture-A",
            languages=["cpp17", "python3"],
            artifacts=[dict(path=raw.name, sha256=hashlib.sha256(raw.read_bytes()).hexdigest())],
        )
        (root / (key + ".json")).write_text(json.dumps(record), encoding="utf-8")


def test_evidence_checks_identity_hash_artifacts_and_no_synthetic_acceptance(tmp_path, manifest):
    inventory = registration(tmp_path, manifest)
    # Synthetic fixture only exercises structural checks; no actual VM assertions.
    write_evidence(inventory, tmp_path)
    assert verify_evidence(inventory, tmp_path) == ()
    (tmp_path / "V-02.txt").write_bytes(b"tampered")
    assert verify_evidence(inventory, tmp_path) == ("MISSING_OR_INVALID_V-02",)
    path = tmp_path / "V-03.json"
    record = json.loads(path.read_text())
    record["synthetic"] = True
    path.write_text(json.dumps(record))
    assert "MISSING_OR_INVALID_V-03" in verify_evidence(inventory, tmp_path)
    record["synthetic"] = False
    record["artifacts"][0]["path"] = "../outside-private.txt"
    path.write_text(json.dumps(record))
    assert "MISSING_OR_INVALID_V-03" in verify_evidence(inventory, tmp_path)


def test_probe_is_only_get_to_fixed_origins_and_binds_supervisor(tmp_path, manifest, monkeypatch):
    inventory = registration(tmp_path, manifest)
    monkeypatch.setenv("ASTRA_JUDGE_TOKEN", "a" * 32)
    monkeypatch.setenv("ASTRA_SUPERVISOR_TOKEN", "s" * 32)
    calls = []

    def handle(req):
        calls.append(req)
        assert req.method == "GET"
        if req.url.path == "/about":
            return httpx.Response(200, json={"version": "synthetic-version"})
        if req.url.path == "/languages":
            return httpx.Response(
                200,
                json=[
                    {"id": 733, "name": "synthetic-python"},
                    {"id": 912, "name": "synthetic-cpp"},
                ],
            )
        if req.url.path == "/config_info":
            return httpx.Response(
                200, json={"enable_network": False, "allow_enable_network": False}
            )
        assert req.url.host == "supervisor.internal" and req.url.path == "/v1/capabilities"
        return httpx.Response(
            200,
            json=dict(
                protocol="astra-supervisor-v1",
                deployment_id=inventory.deployment_id,
                judge_vm_id=inventory.judge_vm_id,
                fingerprint=inventory.fingerprint,
                capabilities=sorted(CAPABILITIES),
            ),
        )

    result = probe_inventory(inventory, transport=httpx.MockTransport(handle))
    assert result.matched and len(calls) == 4
    assert len(verify_evidence(inventory, tmp_path)) == 6  # probe does not manufacture evidence


def test_probe_drift_failure_and_missing_secrets_are_safe(tmp_path, manifest, monkeypatch):
    inventory = registration(tmp_path, manifest)
    monkeypatch.delenv("ASTRA_JUDGE_TOKEN", raising=False)
    with pytest.raises(ExecutionError, match="JUDGE_CREDENTIALS_UNAVAILABLE"):
        probe_inventory(
            inventory, transport=httpx.MockTransport(lambda _: httpx.Response(200, json={}))
        )
    monkeypatch.setenv("ASTRA_JUDGE_TOKEN", "a" * 32)
    monkeypatch.setenv("ASTRA_SUPERVISOR_TOKEN", "s" * 32)
    with pytest.raises(ExecutionError, match="JUDGE_PROBE_FAILED"):
        probe_inventory(
            inventory,
            transport=httpx.MockTransport(
                lambda req: (_ for _ in ()).throw(httpx.ConnectError("PRIVATE", request=req))
            ),
        )
    result = probe_inventory(
        inventory, transport=httpx.MockTransport(lambda _: httpx.Response(200, json={}))
    )
    assert not result.matched


@pytest.mark.parametrize(
    "change", ["missing_capability", "other_vm", "other_fingerprint", "redirect"]
)
def test_probe_requires_capabilities_and_exact_vm_binding(tmp_path, manifest, monkeypatch, change):
    inventory = registration(tmp_path, manifest)
    monkeypatch.setenv("ASTRA_JUDGE_TOKEN", "a" * 32)
    monkeypatch.setenv("ASTRA_SUPERVISOR_TOKEN", "s" * 32)

    def handle(req):
        if req.url.path == "/about":
            return httpx.Response(200, json={"version": "synthetic-version"})
        if req.url.path == "/languages":
            return httpx.Response(
                200,
                json=[
                    {"id": 733, "name": "synthetic-python"},
                    {"id": 912, "name": "synthetic-cpp"},
                ],
            )
        if req.url.path == "/config_info":
            return httpx.Response(
                200, json={"enable_network": False, "allow_enable_network": False}
            )
        if change == "redirect":
            return httpx.Response(307, headers={"Location": "https://other.test"})
        payload = dict(
            protocol="astra-supervisor-v1",
            deployment_id=inventory.deployment_id,
            judge_vm_id=inventory.judge_vm_id,
            fingerprint=inventory.fingerprint,
            capabilities=sorted(CAPABILITIES),
        )
        if change == "missing_capability":
            payload["capabilities"].pop()
        if change == "other_vm":
            payload["judge_vm_id"] = inventory.business_vm_id
        if change == "other_fingerprint":
            payload["fingerprint"] = "0" * 64
        return httpx.Response(200, json=payload)

    if change == "redirect":
        with pytest.raises(ExecutionError, match="JUDGE_PROBE_FAILED"):
            probe_inventory(inventory, transport=httpx.MockTransport(handle))
    else:
        assert not probe_inventory(inventory, transport=httpx.MockTransport(handle)).matched


def test_cli_never_reports_execution_ready_and_template_fails(tmp_path, manifest):
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    path = tmp_path / "deployment.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    command = [sys.executable, str(root / "tools" / "verify_judge.py"), "--registration", str(path)]
    result = subprocess.run(command, capture_output=True, encoding="utf-8", timeout=15)
    payload = json.loads(result.stdout)
    assert result.returncode == 2 and payload["state"] == "BLOCKED"
    assert payload["network_called"] is False and payload["execution_enabled"] is False
    inventory = load_inventory(path)
    write_evidence(inventory, tmp_path)
    result = subprocess.run(
        command + ["--evidence", str(tmp_path)], capture_output=True, encoding="utf-8", timeout=15
    )
    payload = json.loads(result.stdout)
    assert result.returncode == 0 and payload["state"] == "RECORDED_REQUIRES_MEMBER_REVIEW"
    assert payload["execution_enabled"] is False
    template = root / "infra" / "judge" / "deployment.example.json"
    assert template.is_file()
    result = subprocess.run(
        [sys.executable, str(root / "tools" / "verify_judge.py"), "--registration", str(template)],
        capture_output=True,
        encoding="utf-8",
        timeout=15,
    )
    assert result.returncode == 2 and json.loads(result.stdout)["state"] == "UNVERIFIED"


@pytest.mark.parametrize("raw", [b'{"x":1e400}', b'{"x":NaN}', b'{"x":Infinity}', b'{"x":1,"x":2}'])
def test_registration_json_rejects_nonfinite_and_duplicate_fields(raw):
    from app.adapters.judge0 import strict_json

    with pytest.raises(ExecutionError):
        strict_json(raw)


@pytest.mark.parametrize(
    "origin",
    ["https://localhost.", "https://ce.judge0.com.", "https://127.1", "https://[::ffff:127.0.0.1]"],
)
def test_registration_rejects_loopback_aliases_and_public_demo(tmp_path, manifest, origin):
    manifest["management_origin"] = origin
    with pytest.raises(ExecutionError):
        registration(tmp_path, manifest)


def test_unreadable_evidence_directory_returns_safe_failure(tmp_path, manifest, monkeypatch):
    from pathlib import Path

    inventory = registration(tmp_path, manifest)

    def unavailable(_self, **_kwargs):
        raise OSError("PRIVATE_FILESYSTEM_DETAIL")

    monkeypatch.setattr(Path, "resolve", unavailable)
    assert verify_evidence(inventory, tmp_path) == ("INVALID_EVIDENCE_DIRECTORY",)


@pytest.mark.parametrize("kind", ["unc", "symlink"])
def test_evidence_rejects_external_paths_before_resolution(tmp_path, manifest, monkeypatch, kind):
    from pathlib import Path

    inventory = registration(tmp_path, manifest)
    write_evidence(inventory, tmp_path)
    record = tmp_path / "V-01.json"
    value = json.loads(record.read_text())
    value["artifacts"][0]["path"] = (
        r"\\unregistered.invalid\share\observation" if kind == "unc" else "linked/observation"
    )
    record.write_text(json.dumps(value), encoding="utf-8")
    original_resolve, original_symlink = Path.resolve, Path.is_symlink

    def guarded(self, *args, **kwargs):
        if str(self).startswith("\\\\") or "linked" in self.parts:
            raise AssertionError("untrusted path was resolved before rejection")
        return original_resolve(self, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", guarded)
    monkeypatch.setattr(
        Path, "is_symlink", lambda self: self.name == "linked" or original_symlink(self)
    )
    assert verify_evidence(inventory, tmp_path) == ("MISSING_OR_INVALID_V-01",)

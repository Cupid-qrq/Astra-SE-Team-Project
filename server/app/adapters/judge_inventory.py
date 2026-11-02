"""Local registration and read-only evidence/probe checks. Never enables execution."""

import hashlib
import json
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from types import MappingProxyType
from typing import Any

import httpx

from app.adapters.judge0 import Judge0Target, https_origin, read_json, strict_json
from app.adapters.judge_profiles import MAPPING_VERSION, ProfileCatalog, RuntimeProfile
from app.shared.judge import ExecutionError, digest, sha_value, uuid_value

CAPABILITIES = frozenset(
    {
        "compile_resource_limits",
        "aggregate_run_memory",
        "directory_quota",
        "compile_network_off",
        "run_network_off",
        "run_entities_1",
        "fenced_cleanup",
        "resolve_unknown_create",
    }
)
KEYS = {
    "schema",
    "status",
    "business_vm_id",
    "judge_vm_id",
    "deployment_id",
    "management_origin",
    "supervisor_origin",
    "auth_env",
    "supervisor_auth_env",
    "resources",
    "vm_image",
    "engine_image",
    "os_version",
    "kernel_version",
    "hypervisor",
    "source_sha",
    "mapping_version",
    "profiles",
    "about_hash",
    "languages_hash",
    "config_hash",
}
MAX_FILE = 2 * 1024 * 1024


def _read(path: Path) -> bytes:
    with path.open("rb") as stream:
        raw = stream.read(MAX_FILE + 1)
    if len(raw) > MAX_FILE:
        raise ValueError
    return raw


def _text(value: Any) -> bool:
    return (
        isinstance(value, str)
        and 1 <= len(value) <= 100
        and value.strip() == value
        and all(ord(c) >= 32 for c in value)
    )


@dataclass(frozen=True)
class Inventory:
    business_vm_id: str
    judge_vm_id: str
    deployment_id: str
    management_origin: str
    supervisor_origin: str
    source_sha: str
    fingerprint: str
    resources: Mapping[str, int]
    profiles: tuple[RuntimeProfile, ...]
    expected_hashes: Mapping[str, str]
    _json: str = field(repr=False)


def load_inventory(path: Path) -> Inventory:
    try:
        value = strict_json(_read(path))
        if not isinstance(value, dict) or set(value) != KEYS:
            raise ValueError
        if value["schema"] != "astra-judge-registration-v1" or value["status"] != "REGISTERED":
            raise ValueError
        ids = [uuid_value(value[k]) for k in ("business_vm_id", "judge_vm_id", "deployment_id")]
        if ids[0] == ids[1] or value["mapping_version"] != MAPPING_VERSION:
            raise ValueError
        management, supervisor = (
            https_origin(value[k]) for k in ("management_origin", "supervisor_origin")
        )
        if (
            value["auth_env"] != "ASTRA_JUDGE_TOKEN"
            or value["supervisor_auth_env"] != "ASTRA_SUPERVISOR_TOKEN"
        ):
            raise ValueError
        resources = value["resources"]
        required = {"vcpu": 4, "memory_bytes": 8589934592, "disk_bytes": 64424509440, "slots": 4}
        if (
            not isinstance(resources, dict)
            or set(resources) != set(required)
            or any(type(resources[k]) is not int or resources[k] < n for k, n in required.items())
            or resources["slots"] != 4
        ):
            raise ValueError
        for k in ("vm_image", "engine_image"):
            if (
                not isinstance(value[k], str)
                or re.fullmatch(r"sha256:[0-9a-f]{64}", value[k]) is None
            ):
                raise ValueError
        if any(not _text(value[k]) for k in ("os_version", "kernel_version", "hypervisor")):
            raise ValueError
        if (
            not isinstance(value["source_sha"], str)
            or re.fullmatch(r"[0-9a-f]{40}", value["source_sha"]) is None
        ):
            raise ValueError
        hashes = {k: sha_value(value[k + "_hash"]) for k in ("about", "languages", "config")}
        records = value["profiles"]
        if not isinstance(records, list) or not 1 <= len(records) <= 10:
            raise ValueError
        profiles = []
        for item in records:
            if not isinstance(item, dict) or set(item) != {"snapshot", "language_ids"}:
                raise ValueError
            profiles.append(RuntimeProfile.from_public(item["snapshot"], item["language_ids"]))
        ProfileCatalog(profiles)
        if {lang.language_key for p in profiles for lang in p.languages} != {"cpp17", "python3"}:
            raise ValueError
        frozen = json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        )
        return Inventory(
            ids[0],
            ids[1],
            ids[2],
            management,
            supervisor,
            value["source_sha"],
            digest(value),
            MappingProxyType(dict(resources)),
            tuple(profiles),
            MappingProxyType(hashes),
            frozen,
        )
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
        pass
    raise ExecutionError("INVALID_JUDGE_REGISTRATION")


def _inside(root: Path, relative: Path) -> Path:
    # Reject anchors before resolution: Windows UNC resolution itself can do network I/O.
    if (
        relative.anchor
        or not relative.parts
        or relative.is_reserved()
        or any(part == ".." or ":" in part for part in relative.parts)
    ):
        raise ValueError
    candidate = root
    for part in relative.parts:
        candidate = candidate / part
        if candidate.is_symlink() or candidate.is_junction():
            raise ValueError
    return candidate


def _artifact(root: Path, item: Any) -> bool:
    if (
        not isinstance(item, dict)
        or set(item) != {"path", "sha256"}
        or not isinstance(item["path"], str)
    ):
        return False
    relative = Path(item["path"])
    candidate = _inside(root, relative)
    if relative.is_absolute() or not candidate.is_relative_to(root) or candidate == root:
        return False
    return hashlib.sha256(_read(candidate)).hexdigest() == sha_value(item["sha256"])


def verify_evidence(inventory: Inventory, directory: Path) -> tuple[str, ...]:
    """Structural/hash validity only. A member must still review actual VM observations."""
    try:
        root = directory.resolve()
    except (OSError, ValueError, RuntimeError):
        return ("INVALID_EVIDENCE_DIRECTORY",)
    issues = []
    for number in range(1, 7):
        key = f"V-{number:02}"
        try:
            report_path = _inside(root, Path(key + ".json"))
            if not report_path.is_relative_to(root):
                raise ValueError
            value = strict_json(_read(report_path))
            if not isinstance(value, dict) or set(value) != {
                "schema",
                "test_id",
                "result",
                "synthetic",
                "fingerprint",
                "source_sha",
                "performed_at",
                "operator",
                "reviewer",
                "languages",
                "artifacts",
            }:
                raise ValueError
            when = datetime.fromisoformat(value["performed_at"].replace("Z", "+00:00"))
            if (
                value["schema"] != "astra-isolation-evidence-v1"
                or value["test_id"] != key
                or value["result"] != "PASS"
                or value["synthetic"] is not False
                or value["fingerprint"] != inventory.fingerprint
                or value["source_sha"] != inventory.source_sha
                or when.utcoffset() != timedelta(0)
                or any(not _text(value[k]) for k in ("operator", "reviewer"))
                or value["operator"] == value["reviewer"]
                or value["languages"] != ["cpp17", "python3"]
                or not isinstance(value["artifacts"], list)
                or not 1 <= len(value["artifacts"]) <= 20
                or not all(_artifact(root, item) for item in value["artifacts"])
            ):
                raise ValueError
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            issues.append("MISSING_OR_INVALID_" + key)
    return tuple(issues)


@dataclass(frozen=True)
class ProbeResult:
    matched: bool
    observed_hashes: Mapping[str, str]


def _probe_target(inventory: Inventory) -> Judge0Target:
    try:
        return Judge0Target(
            inventory.management_origin,
            inventory.supervisor_origin,
            inventory.deployment_id,
            os.environ["ASTRA_JUDGE_TOKEN"],
            os.environ["ASTRA_SUPERVISOR_TOKEN"],
        )
    except (KeyError, ExecutionError):
        pass
    raise ExecutionError("JUDGE_CREDENTIALS_UNAVAILABLE")


def probe_inventory(
    inventory: Inventory, *, transport: httpx.BaseTransport | None = None
) -> ProbeResult:
    """GET only; declared capabilities/configuration are not physical isolation proof."""
    target = _probe_target(inventory)
    try:
        limits = httpx.Limits(max_connections=1, max_keepalive_connections=1)
        with httpx.Client(
            verify=True,
            trust_env=False,
            follow_redirects=False,
            timeout=5.0,
            transport=transport
            if transport is not None
            else httpx.HTTPTransport(verify=True, trust_env=False, retries=0, limits=limits),
        ) as client:
            values = {}
            for key, path in (
                ("about", "/about"),
                ("languages", "/languages"),
                ("config", "/config_info"),
            ):
                status, value = read_json(
                    client,
                    "GET",
                    target.management_origin + path,
                    headers={"X-Auth-Token": target.auth_token},
                )
                if status != 200:
                    raise ValueError
                values[key] = value
            status, supervisor = read_json(
                client,
                "GET",
                target.supervisor_origin + "/v1/capabilities",
                headers={"Authorization": "Bearer " + target.supervisor_token},
            )
            if status != 200:
                raise ValueError
        observed = {k: digest(v) for k, v in values.items()}
        ids = (
            {
                v["id"]
                for v in values["languages"]
                if isinstance(v, dict) and type(v.get("id")) is int
            }
            if isinstance(values["languages"], list)
            else set()
        )
        needed = {language.language_id for p in inventory.profiles for language in p.languages}
        config = values["config"]
        matched = (
            observed == dict(inventory.expected_hashes)
            and needed <= ids
            and isinstance(config, dict)
            and config.get("enable_network") is False
            and config.get("allow_enable_network") is False
            and isinstance(supervisor, dict)
            and supervisor.get("protocol") == "astra-supervisor-v1"
            and supervisor.get("deployment_id") == inventory.deployment_id
            and supervisor.get("judge_vm_id") == inventory.judge_vm_id
            and supervisor.get("fingerprint") == inventory.fingerprint
            and isinstance(supervisor.get("capabilities"), list)
            and CAPABILITIES <= set(supervisor["capabilities"])
        )
        return ProbeResult(matched, MappingProxyType(observed))
    except (httpx.HTTPError, ValueError, TypeError, KeyError, ExecutionError):
        pass
    raise ExecutionError("JUDGE_PROBE_FAILED")

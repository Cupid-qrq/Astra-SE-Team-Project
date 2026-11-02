"""Deployment-owned execution profile allowlist, bound to A's canonical digest."""

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from app.modules.problems.domain import profile_digest
from app.shared.judge import ExecutionError, LanguageKey, uuid_value

LIMITS = {
    "memory_bytes": 268435456,
    "output_bytes": 1048576,
    "directory_bytes": 33554432,
    "run_entities": 1,
    "compile_timeout_ms": 20000,
    "compile_memory_bytes": 536870912,
    "compile_entities": 30,
}
LANGUAGE_LIMITS = {"cpp17": (2000, 5000), "python3": (4000, 10000)}
MAPPING_VERSION = "astra-judge0-ce-v1"


@dataclass(frozen=True)
class RuntimeLanguage:
    language_key: LanguageKey
    language_id: int
    version: str
    image_digest: str
    cpu_ms: int
    wall_ms: int


@dataclass(frozen=True)
class RuntimeProfile:
    profile_id: str
    profile_hash: str
    languages: tuple[RuntimeLanguage, ...]
    _public_json: str = field(repr=False)

    @classmethod
    def from_public(cls, value: Mapping[str, Any], ids: Mapping[str, int]) -> "RuntimeProfile":
        try:
            if set(value) != {*LIMITS, "comparison", "profile_id", "languages"}:
                raise ValueError
            if any(
                type(value[k]) is not int or value[k] != expected for k, expected in LIMITS.items()
            ):
                raise ValueError
            if value["comparison"] != "ASCII_TOKENS":
                raise ValueError
            profile_id = uuid_value(value["profile_id"])
            records = value["languages"]
            if not isinstance(records, list) or not 1 <= len(records) <= 2:
                raise ValueError
            languages = []
            seen = set()
            for record in records:
                if set(record) != {
                    "language_key",
                    "version",
                    "image_digest",
                    "cpu_time_ms",
                    "wall_time_ms",
                }:
                    raise ValueError
                key = record["language_key"]
                if key not in LANGUAGE_LIMITS or key in seen:
                    raise ValueError
                seen.add(key)
                cpu, wall = LANGUAGE_LIMITS[key]
                if (
                    type(record["cpu_time_ms"]) is not int
                    or type(record["wall_time_ms"]) is not int
                    or (record["cpu_time_ms"], record["wall_time_ms"]) != (cpu, wall)
                ):
                    raise ValueError
                if type(ids[key]) is not int or ids[key] <= 0:
                    raise ValueError
                version = record["version"]
                image = record["image_digest"]
                if (
                    not isinstance(version, str)
                    or not 1 <= len(version) <= 100
                    or any(ord(c) < 32 for c in version)
                ):
                    raise ValueError
                if (
                    not isinstance(image, str)
                    or re.fullmatch(r"sha256:[0-9a-f]{64}", image) is None
                ):
                    raise ValueError
                languages.append(RuntimeLanguage(key, ids[key], version, image, cpu, wall))
            if set(ids) != seen or len(set(ids.values())) != len(ids):
                raise ValueError
            public_json = json.dumps(
                dict(value),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            )
            return cls(profile_id, profile_digest(dict(value)), tuple(languages), public_json)
        except (ValueError, KeyError, TypeError, AttributeError):
            raise ExecutionError("INVALID_EXECUTION_PROFILE") from None

    def public_snapshot(self) -> dict[str, Any]:
        return dict(json.loads(self._public_json))

    def language(self, key: str) -> RuntimeLanguage:
        for language in self.languages:
            if language.language_key == key:
                return language
        raise ExecutionError("INVALID_EXECUTION_LANGUAGE")


class ProfileCatalog:
    def __init__(self, profiles: Sequence[RuntimeProfile]) -> None:
        items = {p.profile_id: p for p in profiles}
        if not profiles or len(items) != len(profiles):
            raise ExecutionError("INVALID_EXECUTION_CATALOG")
        self.profiles: Mapping[str, RuntimeProfile] = MappingProxyType(items)

    def require(self, profile_id: str, profile_hash: str, language_key: str) -> RuntimeProfile:
        profile = self.profiles.get(profile_id)
        if profile is None or profile.profile_hash != profile_hash:
            raise ExecutionError("EXECUTION_PROFILE_NOT_ALLOWED")
        profile.language(language_key)
        return profile

    def bind(self, snapshot: Mapping[str, Any]) -> RuntimeProfile:
        try:
            profile = self.profiles.get(snapshot["profile_id"])
            if profile is None or profile.profile_hash != profile_digest(dict(snapshot)):
                raise ValueError
            return profile
        except (ValueError, TypeError, KeyError):
            raise ExecutionError("EXECUTION_PROFILE_NOT_ALLOWED") from None

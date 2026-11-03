"""Freeze A's preflight snapshot without executing or exposing private materials."""

import json
from dataclasses import dataclass, field

from app.adapters.judge_profiles import ProfileCatalog, SnapshotCatalog
from app.modules.identity.domain import Fault
from app.modules.identity.ports import Record
from app.modules.problems.domain import (
    CONTENT_FIELDS,
    content_digest,
    profile_digest,
    publishable,
    validate_content,
    validate_text,
)
from app.shared.judge import ExecutionError, uuid_value

CaseKey = tuple[str, str, int]


@dataclass(frozen=True)
class FrozenPreflight:
    version_id: str
    version_revision: int
    content_digest: str
    profile_hash: str
    cases: tuple[CaseKey, ...]
    blob: bytes = field(repr=False)


def freeze_snapshot(snapshot: Record, catalog: ProfileCatalog | SnapshotCatalog) -> FrozenPreflight:
    fault = (409, "PREFLIGHT_INVALID", "预检内容不完整或运行环境不匹配，请核对后重试。")
    try:
        version_id = uuid_value(snapshot["version_id"])
        revision = snapshot["revision"]
        if type(revision) is not int or revision < 1:
            raise ValueError
        runtime = catalog.bind(snapshot["profile"])
        validate_content(snapshot)
        publishable(snapshot)
        samples, tests, references = (
            snapshot["samples"],
            snapshot["testcases"],
            snapshot["references"],
        )
        if not 1 <= len(samples) <= 3:
            raise ValueError
        for sample in samples:
            if set(sample) != {"input", "output"}:
                raise ValueError
            for value in sample.values():
                if not isinstance(value, str) or len(value.encode("utf-8")) > 4096:
                    raise ValueError
        for case in tests:
            if (
                set(case) != {"order", "input_text", "answer_text"}
                or type(case["order"]) is not int
            ):
                raise ValueError
            validate_text(case["input_text"], "测试输入")
            validate_text(case["answer_text"], "预期答案")
        languages = {lang.language_key for lang in runtime.languages}
        if (
            len(references) != len(languages)
            or {ref["language_key"] for ref in references} != languages
        ):
            raise ValueError
        for ref in references:
            if set(ref) != {"language_key", "code"} or not ref["code"].strip():
                raise ValueError
            validate_text(ref["code"], "参考程序")
        frozen = {k: snapshot[k] for k in (*CONTENT_FIELDS, "testcases", "references")}
        frozen.update(version_id=version_id, revision=revision)
        blob = json.dumps(
            frozen, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode("utf-8")
        if len(blob) > 16 * 1024 * 1024:
            raise ValueError
        keys = tuple(
            (lang.language_key, kind, order)
            for lang in runtime.languages
            for kind, count in (("SAMPLE", len(samples)), ("HIDDEN", len(tests)))
            for order in range(1, count + 1)
        )
        return FrozenPreflight(
            version_id,
            revision,
            content_digest(frozen),
            profile_digest(frozen["profile"]),
            keys,
            blob,
        )
    except Fault as error:
        fault = (error.status, error.code, error.message)
    except (ExecutionError, KeyError, ValueError, TypeError, AttributeError, UnicodeError):
        pass
    # No captured JSON/UTF-8 exception may remain in the public error's chain.
    raise Fault(*fault)

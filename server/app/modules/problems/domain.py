import hashlib
import json
from typing import Any

from app.modules.identity.domain import byte_limit, require

CONTENT_FIELDS = ("title", "statement", "samples", "tags", "profile", "source_ref")


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    ).hexdigest()


def profile_digest(profile: dict) -> str:
    return canonical_hash(profile)


def content_digest(snapshot: dict) -> str:
    return canonical_hash({k: snapshot[k] for k in (*CONTENT_FIELDS, "testcases", "references")})


def validate_content(value: dict) -> None:
    require(
        bool(value["title"].strip()) and bool(value["statement"].strip()),
        "VALIDATION_ERROR",
        "标题和题面不能为空白。",
        422,
    )
    byte_limit(value["statement"], 32768, "题面")
    for sample in value["samples"]:
        byte_limit(sample["input"], 4096, "样例输入")
        byte_limit(sample["output"], 4096, "样例输出")
    languages = [lang["language_key"] for lang in value["profile"]["languages"]]
    require(len(set(languages)) == len(languages), "VALIDATION_ERROR", "语言环境不能重复。", 422)
    require(
        len(set(value["tags"])) == len(value["tags"]),
        "VALIDATION_ERROR",
        "知识点标签不能重复。",
        422,
    )


def validate_text(value: str, field: str) -> bytes:
    byte_limit(value, 65536, field)
    require(
        not value.startswith("PK\x03\x04"),
        "VALIDATION_ERROR",
        "仅接受UTF-8文本，不接受ZIP文件。",
        422,
    )
    return value.encode("utf-8")


def publishable(snapshot: dict) -> None:
    cases = snapshot["testcases"]
    require(
        1 <= len(cases) <= 10 and [c["order"] for c in cases] == list(range(1, len(cases) + 1)),
        "TESTCASE_GAP",
        "发布前须提供1—10组连续编号的配对测试。",
    )
    languages = {lang["language_key"] for lang in snapshot["profile"]["languages"]}
    require(
        {ref["language_key"] for ref in snapshot["references"]} == languages,
        "REFERENCE_INCOMPLETE",
        "每种允许语言都必须提供参考程序。",
    )


def verify_evidence(snapshot: dict, evidence: dict | None) -> None:
    require(evidence is not None, "PREFLIGHT_INVALID", "预检记录不存在或不匹配。")
    assert evidence
    expected = {
        (lang["language_key"], kind, order)
        for lang in snapshot["profile"]["languages"]
        for kind, count in [
            ("SAMPLE", len(snapshot["samples"])),
            ("HIDDEN", len(snapshot["testcases"])),
        ]
        for order in range(1, count + 1)
    }
    cases = evidence.get("cases", [])
    actual = {(c.get("language_key"), c.get("case_kind"), c.get("case_order")) for c in cases}
    valid = (
        evidence.get("state") == "PASSED"
        and evidence.get("version_id") == snapshot["version_id"]
        and evidence.get("content_digest") == content_digest(snapshot)
        and evidence.get("profile_hash") == profile_digest(snapshot["profile"])
        and expected == actual
        and len(cases) == len(expected)
        and all(c.get("state") == "FINISHED" and c.get("verdict") == "AC" for c in cases)
    )
    require(valid, "PREFLIGHT_INVALID", "预检证据已失效或未覆盖全部语言和测试，请重新预检。")

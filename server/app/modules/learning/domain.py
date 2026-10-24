import hashlib
import json

from app.modules.identity.domain import require
from app.modules.identity.ports import Record

VERDICTS = ("CE", "WA", "TLE", "RE", "SE")


def validate_body(body: Record) -> None:
    title, explanation, checklist = body["title"], body["explanation"], body["checklist"]
    require(
        bool(title.strip()) and len(title) <= 100,
        "VALIDATION_ERROR",
        "帮助标题不能为空且最多100字。",
        422,
    )
    require(bool(explanation.strip()), "VALIDATION_ERROR", "帮助说明不能为空。", 422)
    require(
        len(checklist) <= 10 and all(s.strip() and len(s) <= 500 for s in checklist),
        "VALIDATION_ERROR",
        "检查清单最多10项，每项1—500字。",
        422,
    )
    content = title + explanation + "".join(checklist)
    require(
        len(content) <= 2000 and len(content.encode("utf-8")) <= 8192,
        "VALIDATION_ERROR",
        "帮助正文总计最多2000码点、8 KiB。",
        422,
    )


def checksum(body: Record) -> str:
    validate_body(body)
    return hashlib.sha256(
        json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def public_version(row: Record) -> Record:
    return {
        "feedback_version_id": row["version_id"],
        **{k: row[k] for k in ("title", "explanation", "checklist")},
    }

import base64
import hmac
import json
from pathlib import Path
from typing import Any

from app.modules.identity.domain import Fault, require
from jsonschema import Draft202012Validator, FormatChecker

SPEC = json.loads(
    (Path(__file__).resolve().parents[3] / "specs/openapi/a.openapi.json").read_text(
        encoding="utf-8"
    )
)


def validate(schema: dict, value: Any) -> None:
    validator = Draft202012Validator(
        {**schema, "components": SPEC["components"]}, format_checker=FormatChecker()
    )
    errors = list(validator.iter_errors(value))
    if errors:
        # Never include rejected values, passwords, code or hidden input in errors.
        fields = [
            {
                "field": ".".join(str(p) for p in error.absolute_path)[:100] or "request",
                "message": "字段格式或范围不符合接口要求。",
            }
            for error in errors[:100]
        ]
        raise Fault(422, "VALIDATION_ERROR", "请检查填写内容。", fields=fields)


def page(rows: list[dict], key: str, query: dict[str, str], scope: str, secret: bytes) -> dict:
    require(not (set(query) - {"cursor", "limit"}), "VALIDATION_ERROR", "未知查询参数。", 422)
    try:
        limit = int(query.get("limit", "20"))
        require(1 <= limit <= 100, "VALIDATION_ERROR", "每页数量应为1—100。", 422)
    except ValueError:
        raise Fault(422, "VALIDATION_ERROR", "每页数量无效。") from None
    ordered = sorted(rows, key=lambda r: str(r[key]))
    cursor = query.get("cursor")
    if cursor:
        try:
            require(len(cursor) <= 2048, "VALIDATION_ERROR", "游标无效。", 422)
            data, signature = cursor.split(".")
            expected = hmac.new(secret, data.encode(), "sha256").hexdigest()
            value = json.loads(base64.urlsafe_b64decode(data))
            require(
                hmac.compare_digest(signature, expected) and value["scope"] == scope,
                "VALIDATION_ERROR",
                "游标无效。",
                422,
            )
            require(
                any(str(r[key]) == value["after"] for r in ordered),
                "VALIDATION_ERROR",
                "游标已失效。",
                422,
            )
            ordered = [r for r in ordered if str(r[key]) > value["after"]]
        except (ValueError, KeyError, TypeError):
            raise Fault(422, "VALIDATION_ERROR", "游标无效。") from None
    items = ordered[:limit]
    next_cursor = None
    if len(ordered) > limit:
        data = base64.urlsafe_b64encode(
            json.dumps({"scope": scope, "after": str(items[-1][key])}).encode()
        ).decode()
        next_cursor = data + "." + hmac.new(secret, data.encode(), "sha256").hexdigest()
    return {"items": items, "next_cursor": next_cursor}

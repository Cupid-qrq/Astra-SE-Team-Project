"""Canonical schema validation and signed, scoped pagination."""

import base64
import hmac
import json
from itertools import islice
from pathlib import Path
from typing import Any

from fastapi import Request
from jsonschema import Draft202012Validator, FormatChecker

from app.modules.identity.domain import Fault, require
from app.modules.identity.ports import Record

# Explicitly non-text storage: hashed passwords and UTF-8 bytes persisted as bytea.
# New operations must classify their bytea/hashed fields here, not exempt by field name alone.
NON_TEXT_FIELDS: dict[str, frozenset[str]] = {
    "login": frozenset({"password"}),
    "changePassword": frozenset({"current_password", "new_password"}),
    "createUser": frozenset({"initial_password"}),
    "resetPassword": frozenset({"one_time_password"}),
    "putTestcase": frozenset({"input_text", "answer_text"}),
    "putReference": frozenset({"code"}),
}


def text_storage(value: Any, field: str = "", excluded: frozenset[str] = frozenset()) -> None:
    def invalid() -> None:
        raise Fault(
            422,
            "VALIDATION_ERROR",
            "请检查填写内容。",
            fields=[{"field": field[:100] or "request", "message": "字段包含不可存储的文本字符。"}],
        )

    if isinstance(value, str):
        if "\x00" in value:
            invalid()
    elif isinstance(value, dict):
        for key, item in value.items():
            if key in excluded:
                continue
            if "\x00" in key:
                invalid()
            text_storage(item, f"{field}.{key}" if field else key)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            text_storage(item, f"{field}.{index}" if field else str(index))


class Contract:
    def __init__(self, document: Record) -> None:
        self.document = document

    @classmethod
    def load(cls) -> "Contract":
        relative = Path("specs/openapi.yaml")
        source = next(
            (p / relative for p in Path(__file__).resolve().parents if (p / relative).is_file()),
            None,
        )
        if source is None:
            raise ValueError("Canonical API contract is missing.")
        return cls(json.loads(source.read_text(encoding="utf-8")))

    def validate(self, schema: Record, value: Any) -> None:
        validator = Draft202012Validator(
            {**schema, "components": self.document["components"]}, format_checker=FormatChecker()
        )
        errors = list(islice(validator.iter_errors(value), 100))
        if errors:
            raise Fault(
                422,
                "VALIDATION_ERROR",
                "请检查填写内容。",
                fields=[
                    {
                        "field": ".".join(str(p) for p in e.absolute_path)[:100] or "request",
                        "message": "字段格式或范围不符合接口要求。",
                    }
                    for e in errors
                ],
            )

    def request(self, operation: Record, request: Request, body: Any) -> None:
        if "requestBody" in operation:
            self.validate(operation["requestBody"]["content"]["application/json"]["schema"], body)
            text_storage(body, excluded=NON_TEXT_FIELDS.get(operation["operationId"], frozenset()))
        parameters = operation.get("parameters", [])
        allowed = {p["name"] for p in parameters if p["in"] == "query"}
        require(
            not (set(request.query_params) - allowed), "VALIDATION_ERROR", "未知查询参数。", 422
        )
        require(
            len(request.query_params.multi_items()) == len(request.query_params),
            "VALIDATION_ERROR",
            "查询参数不得重复。",
            422,
        )
        for p in parameters:
            source = {
                "path": request.path_params,
                "query": request.query_params,
                "header": request.headers,
            }.get(p["in"])
            if source is None:
                continue
            value = source.get(p["name"])
            if value is None:
                require(not p.get("required", False), "VALIDATION_ERROR", "缺少必填参数。", 422)
                continue
            schema = p["schema"]
            if schema.get("type") == "integer":
                require(
                    isinstance(value, str) and value.isascii() and value.isdigit(),
                    "VALIDATION_ERROR",
                    "参数数值无效。",
                    422,
                )
                value = int(value)
            self.validate(schema, value)
            if p["in"] in ("query", "path"):
                text_storage(value, p["name"])

    def response(self, operation: Record, status: int, result: Any) -> None:
        schema = (
            operation["responses"][str(status)]
            .get("content", {})
            .get("application/json", {})
            .get("schema")
        )
        if schema:
            try:
                self.validate(schema, result)
            except Fault:
                raise Fault(500, "RESPONSE_CONTRACT_ERROR", "响应校验失败。") from None


def unique_object(pairs: list[tuple[str, Any]]) -> Record:
    result: Record = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def invalid_constant(value: str) -> Any:
    raise ValueError("Non-finite JSON number")


def parse_body(raw: bytes, operation: Record, content_type: str) -> Any:
    if "requestBody" not in operation:
        require(not raw, "VALIDATION_ERROR", "该操作不接受请求正文。", 422)
        return None
    require(
        content_type.split(";", 1)[0].strip().lower() == "application/json",
        "INVALID_REQUEST",
        "请求正文必须为UTF-8 JSON。",
        400,
    )
    try:
        body = json.loads(
            raw.decode("utf-8"), object_pairs_hook=unique_object, parse_constant=invalid_constant
        )
        json.dumps(body, ensure_ascii=False).encode("utf-8")
        return body
    except (ValueError, UnicodeError, RecursionError):
        raise Fault(400, "INVALID_REQUEST", "请求必须为有效UTF-8 JSON且字段不得重复。") from None


class Cursor:
    def __init__(self, query: dict[str, str], scope: str, secret: bytes) -> None:
        self.limit = int(query.get("limit", "20"))
        require(1 <= self.limit <= 100, "VALIDATION_ERROR", "每页数量应为1—100。", 422)
        self.scope, self.secret = scope, secret
        self.after: str | None = None
        cursor = query.get("cursor")
        if cursor:
            try:
                require(len(cursor) <= 2048, "VALIDATION_ERROR", "游标无效。", 422)
                data, signature = cursor.split(".", 1)
                expected = hmac.new(secret, data.encode(), "sha256").hexdigest()
                require(
                    hmac.compare_digest(signature, expected), "VALIDATION_ERROR", "游标无效。", 422
                )
                value = json.loads(base64.urlsafe_b64decode(data))
                require(
                    value["scope"] == scope and isinstance(value["after"], str),
                    "VALIDATION_ERROR",
                    "游标无效。",
                    422,
                )
                self.after = value["after"]
            except (ValueError, KeyError, TypeError):
                raise Fault(422, "VALIDATION_ERROR", "游标无效。") from None

    def finish(self, rows: list[Record], key: str) -> Record:
        items = rows[: self.limit]
        next_cursor = None
        if len(rows) > self.limit:
            data = base64.urlsafe_b64encode(
                json.dumps(
                    {"scope": self.scope, "after": str(items[-1][key])}, separators=(",", ":")
                ).encode()
            ).decode()
            next_cursor = data + "." + hmac.new(self.secret, data.encode(), "sha256").hexdigest()
        return dict(items=items, next_cursor=next_cursor)

    def bounded(self, rows: list[Record], key: str) -> Record:
        ordered = sorted(rows, key=lambda row: row[key])
        if self.after is not None:
            require(
                any(str(row[key]) == self.after for row in ordered),
                "VALIDATION_ERROR",
                "游标已失效。",
                422,
            )
            index = next(i for i, row in enumerate(ordered) if str(row[key]) == self.after)
            ordered = ordered[index + 1 :]
        return self.finish(ordered[: self.limit + 1], key)

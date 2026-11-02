"""Single-call candidate evaluator. No provider, queue, credentials or network client is installed.

A job runner must commit a unique dispatch permit first, call outside its transaction, then
recheck authorization and settle disposition in a new transaction before exposing any sections.
"""

import asyncio
import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Literal, Protocol

from jsonschema import Draft202012Validator

from app.modules.identity.ports import Record

SCHEMAS = Path(__file__).resolve().parents[4] / "specs" / "model"


@lru_cache(maxsize=2)
def _schema(name: str) -> Draft202012Validator:
    return Draft202012Validator(json.loads((SCHEMAS / name).read_text(encoding="utf-8")))


def _valid_context(value: Record) -> bool:
    if not _schema("input.schema.json").is_valid(value):
        return False
    raw = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return len(raw.encode()) <= 24 * 1024 and all(
        len(part.encode()) <= 4096 for sample in value["public_samples"] for part in sample.values()
    )


def prepare_context(source: Record, *, question: str) -> Record:
    """Source is a server-authorized public projection including only the owner's code.

    The upstream adapter owns diagnostic sanitization and sample visibility. Raw judge
    diagnostics and test cases must never be used as a substitute for those fields.
    """
    try:
        value = {
            k: source[k]
            for k in (
                "public_problem",
                "student_code",
                "language_key",
                "sanitized_diagnostic",
                "verdict",
            )
        }
        value.update(
            schema_version="1",
            question=question,
            public_samples=[
                {k: sample[k] for k in ("input", "output")} for sample in source["public_samples"]
            ],
        )
        if _valid_context(value):
            return value
    except (KeyError, TypeError, ValueError):
        pass
    raise ValueError("INVALID_MODEL_CONTEXT")


@dataclass(frozen=True)
class FrozenModel:
    model_version: str
    template_version_id: str
    max_input_tokens: int
    max_output_tokens: int
    provider_model_id: str | None = None
    config_id: str | None = None
    input_price_ceiling: Decimal | None = None
    output_price: Decimal | None = None


@dataclass(frozen=True)
class ModelReply:
    raw: str = field(repr=False)
    actual_cost_cny: Decimal | None
    usage: dict[str, int] | None = None
    provider_request_id: str | None = field(default=None, repr=False)


class ModelTransport(Protocol):
    async def generate(self, context: Record, model: FrozenModel) -> ModelReply:
        """Resolve immutable template, enforce token caps, bound response and honor cancellation."""
        ...


class ModelNotDispatched(Exception):
    """Transport confirms a local refusal before any outbound request."""


class ModelRateLimited(Exception):
    """Provider rate limit. Do not retry. No authoritative cost was received."""


@dataclass(frozen=True)
class Candidate:
    sections: dict[str, str] | None = field(repr=False)
    reason_code: str | None
    billing: Literal["RELEASED", "UNCERTAIN", "SETTLED"]
    actual_cost_cny: Decimal | None
    usage: dict[str, int] | None = None
    provider_request_id: str | None = field(default=None, repr=False)


def _unique_fields(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("DUPLICATE_KEY")
        result[key] = value
    return result


def _sections(raw: str) -> dict[str, str]:
    if not isinstance(raw, str) or len(raw) > 2000 or len(raw.encode()) > 8192:
        raise ValueError("INVALID_MODEL_OUTPUT")
    value = json.loads(raw, object_pairs_hook=_unique_fields)
    if not _schema("output.schema.json").is_valid(value):
        raise ValueError("INVALID_MODEL_OUTPUT")
    # JSON may escape unpaired UTF-16 surrogates that cannot be stored as UTF-8.
    for section in value.values():
        section.encode()
        if "\x00" in section:
            raise ValueError("INVALID_MODEL_OUTPUT")
    return value


async def evaluate_candidate(
    context: Record,
    model: FrozenModel,
    *,
    transport: ModelTransport | None = None,
    content_check: Callable[[dict[str, str]], bool] | None = None,
) -> Candidate:
    """A successful return is only a candidate. Semantic review is explicitly required."""
    if transport is None or content_check is None:
        return Candidate(None, "MODEL_DISABLED", "RELEASED", None)
    if (
        not model.model_version.strip()
        or not model.template_version_id.strip()
        or any(
            type(n) is not int or n <= 0 for n in (model.max_input_tokens, model.max_output_tokens)
        )
    ):
        return Candidate(None, "MODEL_CONFIG_INVALID", "RELEASED", None)
    try:
        if not _valid_context(context):
            return Candidate(None, "INVALID_MODEL_CONTEXT", "RELEASED", None)
    except (ValueError, TypeError):
        return Candidate(None, "INVALID_MODEL_CONTEXT", "RELEASED", None)
    try:
        async with asyncio.timeout(20):
            reply = await transport.generate(context, model)
    except ModelNotDispatched:
        return Candidate(None, "MODEL_NOT_DISPATCHED", "RELEASED", None)
    except TimeoutError:
        return Candidate(None, "MODEL_TIMEOUT", "UNCERTAIN", None)
    except ModelRateLimited:
        return Candidate(None, "MODEL_RATE_LIMITED", "UNCERTAIN", None)
    except Exception:
        return Candidate(None, "MODEL_UNAVAILABLE", "UNCERTAIN", None)
    cost = reply.actual_cost_cny
    if not isinstance(cost, Decimal) or not cost.is_finite() or cost < 0:
        cost = None
    billing: Literal["UNCERTAIN", "SETTLED"] = "UNCERTAIN" if cost is None else "SETTLED"
    usage_keys = (
        "prompt_tokens",
        "completion_tokens",
        "prompt_cache_hit_tokens",
        "prompt_cache_miss_tokens",
    )
    usage = {
        k: reply.usage[k]
        for k in usage_keys
        if isinstance(reply.usage, dict)
        and type(reply.usage.get(k)) is int
        and 0 <= reply.usage[k] <= 2**31 - 1
    }
    request_id = reply.provider_request_id
    if not isinstance(request_id, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", request_id):
        request_id = None
    receipt = Candidate(None, None, billing, cost, usage or None, request_id)
    try:
        sections = _sections(reply.raw)
    except (ValueError, TypeError, RecursionError):
        return replace(receipt, reason_code="INVALID_MODEL_OUTPUT")
    try:
        # Reject active markup and code fences before the caller's semantic safety review.
        safe = (
            not any(
                re.search(r"```|<\s*/?\s*[a-zA-Z][\w:-]*(?:\s[^>]*)?>", s)
                for s in sections.values()
            )
            and content_check(sections.copy()) is True
        )
    except Exception:
        safe = False
    return (
        replace(receipt, sections=sections)
        if safe
        else replace(receipt, reason_code="SAFETY_BLOCKED")
    )

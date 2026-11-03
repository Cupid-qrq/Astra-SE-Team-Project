"""Explicit official Flash profile. Loading configuration never reads credentials or calls HTTP.

The UTF-8 byte bound plus framing allowance is deliberately conservative, not an exact
official tokenizer. Pricing is a verified peak ceiling; off-peak billing may be lower.
Usage-derived estimates are never treated as authoritative supplier charges.
"""

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import httpx

from app.adapters.deepseek import DeepSeekTransport, PriceSnapshot
from app.adapters.judge0 import strict_json
from app.modules.identity.ports import Record, Repository

from .model_worker import FrozenModel
from .output_safety import has_forbidden_markup

PRICES = PriceSnapshot(Decimal("0.04"), Decimal("2"), Decimal("8"))


def conservative_tokens(messages: list[dict[str, str]]) -> int:
    """For the supported byte-level Flash tokenizer: <= one token per UTF-8 byte.

    Add 256 request-level and 64 per-message tokens for provider framing. Reverify
    this bound before enabling a different model/tokenizer or API message format.
    """
    return 256 + sum(64 + len(json.dumps(m, ensure_ascii=False).encode()) for m in messages)


def _user_environment(name: str) -> str | None:
    if os.name != "nt":
        return None
    import winreg

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
        value, kind = winreg.QueryValueEx(key, name)
    return value if kind == winreg.REG_SZ and isinstance(value, str) else None


@dataclass(frozen=True)
class RuntimeProfile:
    enabled: bool
    model_id: str
    version_label: str
    api_key_env: str
    max_input_tokens: int
    max_output_tokens: int
    price_verified_at: datetime
    terms_review_ref: str
    project_budget_cny: Decimal
    config_id: str

    @classmethod
    def from_file(cls, path: str | Path) -> "RuntimeProfile":
        profile = None
        try:
            with Path(path).open("rb") as stream:
                raw = stream.read(16385)
            if len(raw) > 16384:
                raise ValueError
            data = strict_json(raw)
            keys = {
                "schema_version",
                "enabled",
                "provider",
                "base_url",
                "model_id",
                "version_label",
                "api_key_env",
                "max_input_tokens",
                "max_output_tokens",
                "price_verified_at",
                "terms_review_ref",
                "prices",
                "project_budget_cny",
            }
            if not isinstance(data, dict) or set(data) != keys:
                raise ValueError
            if not (
                data["schema_version"] == "1"
                and type(data["enabled"]) is bool
                and data["provider"] == "deepseek"
                and data["base_url"] == "https://api.deepseek.com"
                and data["model_id"] == "deepseek-flash"
                and isinstance(data["version_label"], str)
                and re.fullmatch(r"[A-Za-z0-9_.:@-]{1,120}", data["version_label"])
                and isinstance(data["api_key_env"], str)
                and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,127}", data["api_key_env"])
                and isinstance(data["terms_review_ref"], str)
                and re.fullmatch(r"[A-Za-z0-9_./:@-]{1,500}", data["terms_review_ref"])
                and type(data["max_input_tokens"]) is int
                and 1024 <= data["max_input_tokens"] <= 131072
                and type(data["max_output_tokens"]) is int
                and 128 <= data["max_output_tokens"] <= 4096
                and data["prices"] == dict(cached_input="0.04", uncached_input="2", output="8")
                and isinstance(data["project_budget_cny"], str)
                and re.fullmatch(
                    r"(?:0|[1-9]|1[0-9]|20)(?:\.[0-9]{1,2})?", data["project_budget_cny"]
                )
                and 0 < Decimal(data["project_budget_cny"]) <= 20
                and data["price_verified_at"] == "2026-11-03T00:00:00Z"
            ):
                raise ValueError
            profile = cls(
                data["enabled"],
                data["model_id"],
                data["version_label"],
                data["api_key_env"],
                data["max_input_tokens"],
                data["max_output_tokens"],
                datetime.fromisoformat(data["price_verified_at"]),
                data["terms_review_ref"],
                Decimal(data["project_budget_cny"]),
                str(uuid5(NAMESPACE_URL, "astra-model:" + json.dumps(data, sort_keys=True))),
            )
        except Exception:
            pass
        if profile is None:
            # Outside the except block: no sensitive parser/path exception chain survives.
            raise ValueError("MODEL_CONFIG_INVALID")
        return profile

    def load_token(self) -> str:
        token = None
        try:
            token = os.environ.get(self.api_key_env)
            if token is None:
                token = _user_environment(self.api_key_env)
            if (
                not isinstance(token, str)
                or not 8 <= len(token) <= 4096
                or any(ord(c) < 33 or ord(c) > 126 for c in token)
            ):
                token = None
        except Exception:
            token = None
        if token is None:
            raise ValueError("MODEL_CREDENTIAL_UNAVAILABLE")
        return token

    @property
    def cost_upper_cny(self) -> Decimal:
        return (
            self.max_input_tokens * PRICES.uncached_input + self.max_output_tokens * PRICES.output
        ) / 1_000_000

    def frozen_model(self, template_id: str) -> FrozenModel:
        return FrozenModel(
            self.version_label,
            template_id,
            self.max_input_tokens,
            self.max_output_tokens,
            self.model_id,
            self.config_id,
            PRICES.uncached_input,
            PRICES.output,
        )

    def transport(
        self,
        template_id: str,
        template: Record,
        *,
        token: str | None = None,
        http_transport: httpx.AsyncBaseTransport | None = None,
    ) -> DeepSeekTransport:
        if not self.enabled:
            raise ValueError("MODEL_DISABLED")
        return DeepSeekTransport(
            token=token if token is not None else self.load_token(),
            model_id=self.model_id,
            template_id=template_id,
            template=template,
            prices=PRICES,
            count_tokens=conservative_tokens,
            transport=http_transport,
            config_id=self.config_id,
            version_label=self.version_label,
            conservative_billing=True,
        )

    def record(self) -> Record:
        return dict(
            config_id=self.config_id,
            provider="deepseek",
            model_id=self.model_id,
            version_label=self.version_label,
            terms_review_ref=self.terms_review_ref,
            price_verified_at=self.price_verified_at,
            input_price=PRICES.uncached_input,
            output_price=PRICES.output,
            max_input_tokens=self.max_input_tokens,
            max_output_tokens=self.max_output_tokens,
            enabled=self.enabled,
        )

    def bootstrap(self, repo: Repository) -> None:
        """Caller owns transaction. Never overwrite config or erase historical liabilities."""
        repo.guard()
        expected = self.record()
        existing = repo.get("model_configs", self.config_id, lock=True)
        if existing is not None and existing != expected:
            raise ValueError("MODEL_CONFIG_CHANGED")
        if existing is None:
            repo.add("model_configs", expected)
        account = repo.get("budget_accounts", "PROJECT", lock=True)
        if account is None:
            repo.add(
                "budget_accounts",
                dict(
                    scope_key="PROJECT",
                    limit_amount=self.project_budget_cny,
                    settled_amount=0,
                    reserved_amount=0,
                    uncertain_amount=0,
                    revision=1,
                ),
            )
        elif account["limit_amount"] > self.project_budget_cny:
            repo.change(
                "budget_accounts",
                "PROJECT",
                limit_amount=self.project_budget_cny,
                revision=account["revision"] + 1,
            )


def content_gate(sections: dict[str, str]) -> bool:
    """Reject obvious code/markup/prompt disclosure. A heuristic, not semantic assurance."""
    blocked = re.compile(
        r"\b(?:def|class)\s+\w+\s*[:(]|\b(?:int|void|auto)\s+main\s*\(|"
        r"(?m:^\s*(?:import\s|from\s+\w+\s+import|#include\s|using namespace))|"
        r"\b(?:os\.system|subprocess\.|eval\s*\(|exec\s*\()|"
        r"完整(?:代码|解答)|参考(?:代码|答案)|系统(?:提示词|指令)(?:如下|是|为)|"
        r"忽略(?:之前|以上|所有).{0,12}指令|hidden[_ ]tests|system prompt",
        re.IGNORECASE,
    )
    return bool(sections) and all(
        isinstance(value, str)
        and bool(value.strip())
        and not has_forbidden_markup(value)
        and not blocked.search(value)
        for value in sections.values()
    )

import asyncio
import json
import logging
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from app.adapters.deepseek import DeepSeekTransport, PriceSnapshot
from app.modules.learning.model_worker import FrozenModel, ModelNotDispatched, ModelRateLimited


def test_transport_pins_destination_template_and_exact_cached_usage():
    requests = []

    def respond(req):
        requests.append(req)
        return httpx.Response(
            200,
            json={
                "choices": [{"finish_reason": "stop", "message": {"content": "{}"}}],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 2,
                    "prompt_cache_hit_tokens": 4,
                    "prompt_cache_miss_tokens": 6,
                },
            },
        )

    adapter = DeepSeekTransport(
        token="fixture",
        model_id="fixture-model",
        template_id="t",
        template={
            "body": "请检查 {verdict}",
            "allowed_placeholders": ["verdict"],
            "schema_version": "1",
        },
        prices=PriceSnapshot(Decimal("1"), Decimal("2"), Decimal("3")),
        count_tokens=lambda messages: 200,
        transport=httpx.MockTransport(respond),
    )
    context = json.loads(
        (Path(__file__).resolve().parents[3] / "specs/model/sample-input.json").read_text(
            encoding="utf8"
        )
    )
    context["verdict"] = "WA"
    reply = asyncio.run(adapter.generate(context, FrozenModel("fixture-model", "t", 256, 64)))
    assert reply.actual_cost_cny == Decimal("0.000022")
    assert str(requests[0].url) == "https://api.deepseek.com/chat/completions"
    body = json.loads(requests[0].content)
    assert body["stream"] is False and body["max_tokens"] == 64
    assert "请检查 WA" in body["messages"][1]["content"]
    assert "请检查 WA" not in body["messages"][0]["content"]


def test_local_cap_rejects_before_network_and_http_logging_is_suppressed(caplog):
    from app.adapters.deepseek import DeepSeekTransport

    calls = []

    def reply(req):
        calls.append(req)
        logging.getLogger("httpcore.http11").debug("synthetic-secret")
        return httpx.Response(429)

    common = dict(
        token="fixture",
        model_id="m",
        template_id="t",
        template={"body": "检查", "allowed_placeholders": [], "schema_version": "1"},
        prices=PriceSnapshot(Decimal(1), Decimal(1), Decimal(1)),
        transport=httpx.MockTransport(reply),
    )
    context = json.loads(
        (Path(__file__).resolve().parents[3] / "specs/model/sample-input.json").read_text(
            encoding="utf8"
        )
    )
    model = FrozenModel("m", "t", 50, 10)
    with pytest.raises(ModelNotDispatched):
        asyncio.run(DeepSeekTransport(**common, count_tokens=lambda _: 51).generate(context, model))
    assert not calls
    with caplog.at_level(logging.DEBUG), pytest.raises(ModelRateLimited):
        asyncio.run(DeepSeekTransport(**common, count_tokens=lambda _: 20).generate(context, model))
    assert "synthetic-secret" not in caplog.text

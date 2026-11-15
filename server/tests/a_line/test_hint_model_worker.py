import asyncio
import json
from dataclasses import replace
from decimal import Decimal

import pytest

from app.modules.learning.model_worker import (
    FrozenModel,
    ModelReply,
    evaluate_candidate,
    prepare_context,
)


def context(**changes):
    value = dict(
        public_problem="求两数之和",
        public_samples=[dict(input="1 2", output="3")],
        student_code="print(2)",
        language_key="python3",
        sanitized_diagnostic="",
        verdict="WA",
        hidden_tests="not-for-model",
        stderr="sensitive",
    )
    return prepare_context(value | changes, question="请给我一个检查方向")


MODEL = FrozenModel("model:fixture", "template-v1", 128, 96)
SECTIONS = dict(
    error_category="可能是格式错误",
    location_clues="查看输出",
    checks="比较空格",
    learning_advice="尝试边界输入",
)


class Transport:
    def __init__(self, raw=None, cost=Decimal("0.01"), failure=None):
        self.calls = 0
        self.raw = json.dumps(SECTIONS, ensure_ascii=False) if raw is None else raw
        self.cost, self.failure = cost, failure

    async def generate(self, context, model):
        self.calls += 1
        if self.failure:
            raise self.failure("sensitive")
        return ModelReply(self.raw, self.cost)


def run(transport=None, model=MODEL, content_check=lambda _: True, data=None):
    return asyncio.run(
        evaluate_candidate(
            context() if data is None else data,
            model,
            transport=transport,
            content_check=content_check,
        )
    )


def test_allowlisted_detached_context_schema_and_bytes():
    sample = dict(input="in", output="out", hidden="private")
    value = context(public_samples=[sample])
    sample["input"] = "mutated"
    assert value["public_samples"] == [dict(input="in", output="out")]
    assert "stderr" not in value and "hidden_tests" not in value
    for changes in (
        dict(public_problem="界" * 9000),
        dict(public_samples=[dict(input="界" * 1600, output="")]),
    ):
        with pytest.raises(ValueError) as invalid:
            context(**changes)
        assert "界" not in str(invalid.value)


def test_worker_disabled_and_invalid_input_do_not_dispatch():
    assert run().billing == "RELEASED"
    tx = Transport()
    for result in (
        run(tx, replace(MODEL, max_output_tokens=0)),
        run(tx, content_check=None),
        run(tx, data=context() | {"hidden": "private"}),
    ):
        assert result.sections is None and result.billing == "RELEASED"
    assert tx.calls == 0


@pytest.mark.parametrize(
    "raw",
    [
        "",
        '{"checks":"x","checks":"y"}',
        "x" * 2001,
        json.dumps(SECTIONS | {"checks": "```python\nprint(1)\n```"}),
        json.dumps(SECTIONS | {"checks": "<script>alert(0)</script>"}),
    ],
)
def test_invalid_outputs_are_discarded_without_releasing_known_cost(raw):
    tx = Transport(raw)
    result = run(tx)
    assert result.sections is None and result.billing == "SETTLED"
    assert result.actual_cost_cny == Decimal("0.01") and tx.calls == 1


def test_uncertain_cost_and_review_gate():
    tx = Transport(failure=TimeoutError)
    outcome = run(tx)
    assert outcome.reason_code == "MODEL_TIMEOUT" and tx.calls == 1
    assert outcome.billing == "UNCERTAIN" and outcome.actual_cost_cny is None
    denied = run(Transport(), content_check=lambda _: False)
    assert denied.sections is None and denied.reason_code == "SAFETY_BLOCKED"
    valid = run(Transport())
    assert valid.sections == SECTIONS
    assert run(Transport(cost=None)).billing == "UNCERTAIN"


def test_preflight_refusal_releases_budget_without_cost():
    from app.modules.learning.model_worker import ModelNotDispatched

    result = run(Transport(failure=ModelNotDispatched))
    assert result.billing == "RELEASED" and result.sections is None


def test_receipt_preserves_only_reconciliation_fields_on_invalid_output():
    from app.modules.learning.model_worker import ModelReply

    class WithReceipt:
        async def generate(self, context, model):
            return ModelReply(
                "invalid",
                None,
                usage={"prompt_tokens": 22, "secret": "private", "completion_tokens": -2},
                provider_request_id="req-fixture_7",
            )

    candidate = run(WithReceipt())
    assert candidate.sections is None and candidate.billing == "UNCERTAIN"
    assert (
        candidate.usage == {"prompt_tokens": 22}
        and candidate.provider_request_id == "req-fixture_7"
    )

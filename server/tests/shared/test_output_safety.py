import asyncio
import json
from decimal import Decimal

import pytest

from app.modules.learning.model_runtime import content_gate
from app.modules.learning.model_worker import (
    FrozenModel,
    ModelReply,
    evaluate_candidate,
    prepare_context,
)


def evaluate(checks, gate):
    sections = dict(
        error_category="检查边界",
        location_clues="查看分配和访问位置",
        checks=checks,
        learning_advice="先手算最小样例",
    )

    class Transport:
        async def generate(self, context, model):
            return ModelReply(json.dumps(sections, ensure_ascii=False), Decimal("0.01"))

    context = prepare_context(
        dict(
            public_problem="检查数组边界",
            public_samples=[dict(input="1", output="1")],
            student_code="int main(){}",
            language_key="cpp17",
            sanitized_diagnostic="",
            verdict="RE",
        ),
        question="",
    )
    return asyncio.run(
        evaluate_candidate(
            context,
            FrozenModel("fixture", "t", 2000, 500),
            transport=Transport(),
            content_check=gate,
        )
    )


@pytest.mark.parametrize(
    "text",
    [
        "检查 vector<int> a(n) 的长度与最后一个访问下标。",
        "检查std::vector<int> a(n) 的长度。",
        "比较 pair<int,int> 中两个值的用途。",
        "检查 std::pair<int, std::string> 的边界。",
    ],
)
@pytest.mark.parametrize("gate", [content_gate, lambda _: True])
def test_recognized_inert_cpp_types_survive_both_candidate_and_runtime_gates(text, gate):
    result = evaluate(text, gate)
    assert result.sections is not None and result.reason_code is None


@pytest.mark.parametrize(
    "text",
    [
        "<int>",
        "<script>alert(1)</script>",
        "vector<script>",
        "vector<int onclick=x>",
        "vector<int><script>alert(1)</script>",
        "std::vector<int> <img src=x onerror=alert(1)>",
        "myvector<int>",
        "pair<script>",
        "vector<int style=color:red>",
    ],
)
@pytest.mark.parametrize("gate", [content_gate, lambda _: True])
def test_unrecognized_types_attributes_and_neighboring_markup_stay_blocked(text, gate):
    result = evaluate(text, gate)
    assert result.sections is None and result.reason_code == "SAFETY_BLOCKED"


def test_complete_cpp_program_stays_blocked_by_runtime_gate():
    result = evaluate("int main() { vector<int> a(1); return 0; }", content_gate)
    assert result.sections is None and result.reason_code == "SAFETY_BLOCKED"

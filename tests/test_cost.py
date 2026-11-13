import pytest

from app.config import INPUT_PRICE_PER_1M, OUTPUT_PRICE_PER_1M
from app.cost import report_cost, step_cost
from app.llm.base import LLMResult


def test_step_cost_exact_for_fixed_tokens():
    expected = round((100 * INPUT_PRICE_PER_1M + 50 * OUTPUT_PRICE_PER_1M) / 1_000_000, 6)
    assert step_cost(100, 50) == expected
    assert step_cost(1_000_000, 0) == round(INPUT_PRICE_PER_1M, 6)
    assert step_cost(0, 1_000_000) == round(OUTPUT_PRICE_PER_1M, 6)


def test_report_cost_is_sum_of_steps():
    steps = [
        LLMResult("a", 100, 50),
        LLMResult("b", 1234, 567),
        {"input_tokens": 10, "output_tokens": 0},
    ]
    expected = round(step_cost(100, 50) + step_cost(1234, 567) + step_cost(10, 0), 6)
    assert report_cost(steps) == expected


def test_zero_tokens_cost_zero():
    assert step_cost(0, 0) == 0
    assert report_cost([]) == 0
    assert report_cost([LLMResult("", 0, 0)]) == 0


def test_negative_tokens_rejected():
    with pytest.raises(ValueError):
        step_cost(-1, 0)

"""Per-step and per-report cost, calculated in code from config prices (USD)."""
from typing import Any, Iterable, Mapping, Union

from app.config import INPUT_PRICE_PER_1M, OUTPUT_PRICE_PER_1M

DECIMALS = 6


def step_cost(input_tokens: int, output_tokens: int) -> float:
    if input_tokens < 0 or output_tokens < 0:
        raise ValueError("token counts cannot be negative")
    cost = (
        input_tokens * INPUT_PRICE_PER_1M + output_tokens * OUTPUT_PRICE_PER_1M
    ) / 1_000_000
    return round(cost, DECIMALS)


def _tokens(step: Union[Any, Mapping[str, int]]) -> tuple[int, int]:
    if isinstance(step, Mapping):
        return step["input_tokens"], step["output_tokens"]
    return step.input_tokens, step.output_tokens


def report_cost(steps: Iterable[Union[Any, Mapping[str, int]]]) -> float:
    """Sum of step costs. Steps are LLMResult-like objects or dicts with token counts."""
    return round(sum(step_cost(*_tokens(s)) for s in steps), DECIMALS)

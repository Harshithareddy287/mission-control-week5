"""Report pipeline: limits -> classify -> brief_by -> checks -> draft/review.

The verdict and violations come ONLY from app.rules.evaluate_limits, which runs
first. They are stored as immutable values and never re-read from, or changed
by, any model output.
"""
import time
from typing import Any, Mapping, Union

from pydantic import BaseModel

from app.briefing import draft_and_review
from app.checks import run_checks
from app.classify import classify
from app.cost import report_cost, step_cost
from app.llm.base import LLMClient
from app.prompts import report_fields
from app.rules import brief_by_minutes, evaluate_limits

PENDING = "pending"  # the only briefing status the pipeline ever sets


def _ms_since(start: float) -> float:
    return round((time.perf_counter() - start) * 1000, 1)


def _step(name: str, input_tokens: int, output_tokens: int, duration_ms: float, summary: str) -> dict:
    return {
        "name": name,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": step_cost(input_tokens, output_tokens),
        "duration_ms": duration_ms,
        "summary": summary,
    }


async def process_report(
    client: LLMClient, report: Union[BaseModel, Mapping[str, Any]]
) -> dict:
    r = report_fields(report)
    trace: list[dict] = []

    # a. Launch limits FIRST, in plain code. Final from here on.
    start = time.perf_counter()
    verdict, violation_list = evaluate_limits(r["wind_knots"], r["temp_c"], r["fuel_pct"])
    violations = tuple(violation_list)  # immutable: nothing below can alter it
    trace.append(_step(
        "limits", 0, 0, _ms_since(start),
        f"{verdict}: " + ("; ".join(violations) if violations else "all readings within limits"),
    ))

    # b. Classify (model). Only subsystem/severity are taken from it.
    start = time.perf_counter()
    classification, llm, fallback = await classify(client, r)
    trace.append(_step(
        "classify", llm.input_tokens, llm.output_tokens, _ms_since(start),
        f"{classification.subsystem} / {classification.severity}"
        + (" (fallback: invalid model reply)" if fallback else ""),
    ))

    # c. Brief-by time (code). Any violation counts as high.
    start = time.perf_counter()
    brief_by = brief_by_minutes(classification.severity, list(violations))
    trace.append(_step("brief_by", 0, 0, _ms_since(start), f"{brief_by} min"))

    # d. Three checks at the same time (model).
    runs = await run_checks(client, r["note"])
    checks = {}
    for name, run in runs.items():
        checks[name.removeprefix("check_")] = run.check.model_dump()
        trace.append(_step(
            name, run.llm.input_tokens, run.llm.output_tokens, run.duration_ms,
            ("flagged: " if run.check.flag else "clear: ") + run.check.reason,
        ))

    # e. Hidden instructions send the report to human review. Verdict untouched.
    needs_review = checks["injection"]["flag"]

    # f. Draft + review loop (model). The briefing is always saved as pending:
    #    only a person can approve it (POST /api/briefings/{id}/approve).
    loop = await draft_and_review(client, {
        "report": r,
        "verdict": verdict,
        "violations": list(violations),
        "classification": {
            "subsystem": classification.subsystem,
            "severity": classification.severity,
            "fallback": fallback,
        },
        "brief_by": brief_by,
        "checks": checks,
        "needs_review": needs_review,
    })
    trace.extend(loop["trace"])
    briefing = {
        "text": loop["final_text"],
        "status": PENDING,
        "rounds": loop["rounds_used"],
        "review_passed": loop["review_passed"],
        "review_exhausted": not loop["review_passed"],  # all MAX_ROUNDS rounds failed
        "needs_review": needs_review,
    }

    return {
        "verdict": verdict,
        "violations": list(violations),
        "subsystem": classification.subsystem,
        "severity": classification.severity,
        "classification_fallback": fallback,
        "brief_by": brief_by,
        "checks": checks,
        "needs_review": needs_review,
        "total_cost": report_cost(trace),
        "steps": trace,
        "briefing": briefing,
    }

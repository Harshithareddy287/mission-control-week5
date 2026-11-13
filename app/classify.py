"""Sort a report by subsystem and severity with a model, validated in code."""
from typing import Any, Literal, Mapping, Union, get_args

from pydantic import BaseModel, ConfigDict, ValidationError

from app.llm.base import LLMClient, LLMResult
from app.prompts import UNTRUSTED_NOTE_RULE, report_fields, wrap_note

Subsystem = Literal["propulsion", "avionics", "telemetry", "ground_systems", "weather", "other"]
Severity = Literal["low", "medium", "high"]
SUBSYSTEMS = list(get_args(Subsystem))
SEVERITIES = list(get_args(Severity))

CLASSIFY_SCHEMA = {
    "type": "object",
    "properties": {
        "subsystem": {"type": "string", "enum": SUBSYSTEMS},
        "severity": {"type": "string", "enum": SEVERITIES},
    },
    "required": ["subsystem", "severity"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = (
    "You sort launch-console anomaly reports for the Flight Director.\n"
    f"Choose exactly one subsystem from: {', '.join(SUBSYSTEMS)}.\n"
    f"Choose exactly one severity from: {', '.join(SEVERITIES)}.\n"
    f"{UNTRUSTED_NOTE_RULE}\n"
    'Reply only with JSON: {"subsystem": "...", "severity": "..."}.'
)


class Classification(BaseModel):
    model_config = ConfigDict(extra="ignore")

    subsystem: Subsystem
    severity: Severity


FALLBACK = Classification(subsystem="other", severity="high")


def build_user_prompt(report: Union[BaseModel, Mapping[str, Any]]) -> str:
    r = report_fields(report)
    return (
        f"Station: {r['station']}\n"
        f"Readings: wind_knots={r['wind_knots']}, temp_c={r['temp_c']}, "
        f"fuel_pct={r['fuel_pct']}\n"
        f"{wrap_note(r['note'])}"
    )


async def classify(
    client: LLMClient, report: Union[BaseModel, Mapping[str, Any]]
) -> tuple[Classification, LLMResult, bool]:
    """Return (classification, raw model result, fallback).

    On ANY failure (call error, bad JSON, value outside the enum, missing field)
    returns subsystem="other", severity="high", fallback=True.
    """
    try:
        result = await client.complete(
            "classify", SYSTEM_PROMPT, build_user_prompt(report), schema=CLASSIFY_SCHEMA
        )
    except Exception:
        return FALLBACK.model_copy(), LLMResult(text="", input_tokens=0, output_tokens=0), True

    try:
        return Classification.model_validate_json(result.text), result, False
    except (ValidationError, ValueError, TypeError):
        return FALLBACK.model_copy(), result, True

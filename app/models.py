"""Request/response models for anomaly reports.

The numeric bounds here are input sanity checks (rejecting impossible readings),
NOT launch limits. Launch limits live only in app/rules.py.
"""
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, Field, StringConstraints

NOTE_MAX_LENGTH = 2000

# field -> (min, max) sanity bounds; also used to build error messages.
RANGES = {
    "wind_knots": (0, 200),
    "temp_c": (-80, 80),
    "fuel_pct": (0, 100),
}

# Human-readable labels for error messages.
FIELD_LABELS = {
    "name": "Name",
    "station": "Station",
    "note": "Note",
    "wind_knots": "Wind (knots)",
    "temp_c": "Temperature (°C)",
    "fuel_pct": "Fuel (%)",
}

RequiredText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
NoteText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=NOTE_MAX_LENGTH)
]


def _bounded(field: str):
    lo, hi = RANGES[field]
    return Field(ge=lo, le=hi, allow_inf_nan=False)


class ReportIn(BaseModel):
    name: RequiredText
    station: RequiredText
    note: NoteText
    wind_knots: float = _bounded("wind_knots")
    temp_c: float = _bounded("temp_c")
    fuel_pct: float = _bounded("fuel_pct")


class CheckOut(BaseModel):
    flag: bool
    reason: str


class StepOut(BaseModel):
    name: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    duration_ms: float
    summary: str


class ReportOut(ReportIn):
    id: int
    created_at: str
    # Pipeline results; None/empty only if a report was saved without them.
    verdict: Optional[Literal["go", "no_go"]] = None
    violations: list[str] = []
    subsystem: Optional[str] = None
    severity: Optional[str] = None
    classification_fallback: Optional[bool] = None
    brief_by: Optional[int] = None
    checks: Optional[dict[str, CheckOut]] = None
    needs_review: Optional[bool] = None
    total_cost: Optional[float] = None
    steps: list[StepOut] = []

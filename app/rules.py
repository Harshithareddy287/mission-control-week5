"""Launch limits and brief-by deadlines.

This module is the ONLY source of the launch verdict and its violations.
It is plain Python: no model calls, no app.llm, no openai. Nothing a model
produces may change what these functions return.
"""
import math

WIND_MAX = 25
TEMP_MIN = 4
FUEL_MIN = 98
FUEL_MAX = 100

BRIEF_BY_MINUTES = {"high": 5, "medium": 15, "low": 30}
BRIEF_BY_DEFAULT = 5  # unknown severity is treated as high (fail safe)


def _fmt(value: float) -> str:
    # 25.0 -> "25", 25.1 -> "25.1"
    return f"{value:g}"


def evaluate_limits(
    wind_knots: float, temp_c: float, fuel_pct: float
) -> tuple[str, list[str]]:
    """Return ("go", []) if every reading is within limits, else ("no_go", violations).

    Limits are inclusive: wind == 25, temp == 4, fuel == 98 or 100 are all "go".
    A reading that is not a finite number is itself a violation (fail safe).
    """
    violations: list[str] = []

    readings = {"wind_knots": wind_knots, "temp_c": temp_c, "fuel_pct": fuel_pct}
    for name, value in readings.items():
        if not math.isfinite(value):
            violations.append(f"{name} {_fmt(value)} is not a valid reading")

    if math.isfinite(wind_knots) and wind_knots > WIND_MAX:
        violations.append(f"wind_knots {_fmt(wind_knots)} exceeds max {WIND_MAX}")
    if math.isfinite(temp_c) and temp_c < TEMP_MIN:
        violations.append(f"temp_c {_fmt(temp_c)} is below min {TEMP_MIN}")
    if math.isfinite(fuel_pct):
        if fuel_pct < FUEL_MIN:
            violations.append(f"fuel_pct {_fmt(fuel_pct)} is below min {FUEL_MIN}")
        elif fuel_pct > FUEL_MAX:
            violations.append(f"fuel_pct {_fmt(fuel_pct)} exceeds max {FUEL_MAX}")

    return ("no_go", violations) if violations else ("go", [])


def brief_by_minutes(severity: str, violations: list[str]) -> int:
    """Minutes until the Flight Director must be briefed.

    Any violation forces the high deadline (5). Otherwise high=5, medium=15,
    low=30, and anything unrecognised falls back to 5.
    """
    if violations:
        return BRIEF_BY_MINUTES["high"]
    key = severity.strip().lower() if isinstance(severity, str) else ""
    return BRIEF_BY_MINUTES.get(key, BRIEF_BY_DEFAULT)

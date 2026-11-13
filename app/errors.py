"""Turn FastAPI/Pydantic validation errors into {"errors": [{"field", "message"}]}."""
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.models import FIELD_LABELS, NOTE_MAX_LENGTH, RANGES

NUMBER_ERRORS = {"float_parsing", "float_type", "finite_number", "int_parsing", "int_type"}
RANGE_ERRORS = {"greater_than_equal", "less_than_equal", "greater_than", "less_than"}


def _field_of(loc) -> str:
    # loc looks like ("body", "wind_knots"); a whole-body problem is ("body",).
    parts = [str(p) for p in loc if p != "body"]
    return parts[0] if parts else "body"


def _message(field: str, err: dict) -> str:
    kind = err.get("type", "")
    label = FIELD_LABELS.get(field, field)

    if field == "body":
        if kind == "json_invalid":
            return "Request body is not valid JSON."
        if kind == "missing":
            return "Request body is required."
        return "Request body must be a JSON object."
    if kind == "missing":
        return f"{label} is required."
    if kind == "string_too_short":
        return f"{label} cannot be empty."
    if kind == "string_too_long":
        return f"{label} must be at most {NOTE_MAX_LENGTH} characters."
    if kind == "string_type":
        return f"{label} must be text."
    if kind in NUMBER_ERRORS:
        return f"{label} must be a number."
    if kind in RANGE_ERRORS and field in RANGES:
        lo, hi = RANGES[field]
        return f"{label} must be between {lo} and {hi}."
    return f"{label}: {err.get('msg', 'invalid value')}."


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = []
    seen = set()
    for err in exc.errors():
        # Malformed JSON reports a character offset as its loc; it's a whole-body problem.
        field = "body" if err.get("type") == "json_invalid" else _field_of(err.get("loc", ()))
        if field in seen:  # one message per field keeps the UI clean
            continue
        seen.add(field)
        errors.append({"field": field, "message": _message(field, err)})
    return JSONResponse(status_code=422, content={"errors": errors})

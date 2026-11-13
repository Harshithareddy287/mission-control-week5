import ast
from pathlib import Path

import pytest

from app import rules
from app.rules import brief_by_minutes, evaluate_limits

NOMINAL = {"wind_knots": 10, "temp_c": 15, "fuel_pct": 99}


def readings(**overrides):
    return {**NOMINAL, **overrides}


@pytest.mark.parametrize(
    "overrides",
    [
        {"wind_knots": 25},
        {"temp_c": 4},
        {"fuel_pct": 98},
        {"fuel_pct": 100},
    ],
    ids=["wind=25", "temp=4", "fuel=98", "fuel=100"],
)
def test_exactly_on_limit_is_go(overrides):
    assert evaluate_limits(**readings(**overrides)) == ("go", [])


@pytest.mark.parametrize(
    "overrides, expected",
    [
        ({"wind_knots": 25.1}, "wind_knots 25.1 exceeds max 25"),
        ({"temp_c": 3.9}, "temp_c 3.9 is below min 4"),
        ({"fuel_pct": 97.9}, "fuel_pct 97.9 is below min 98"),
        ({"fuel_pct": 100.1}, "fuel_pct 100.1 exceeds max 100"),
    ],
    ids=["wind=25.1", "temp=3.9", "fuel=97.9", "fuel=100.1"],
)
def test_just_past_limit_is_no_go(overrides, expected):
    assert evaluate_limits(**readings(**overrides)) == ("no_go", [expected])


def test_several_violations_all_listed():
    verdict, violations = evaluate_limits(wind_knots=40, temp_c=-2, fuel_pct=50)
    assert verdict == "no_go"
    assert violations == [
        "wind_knots 40 exceeds max 25",
        "temp_c -2 is below min 4",
        "fuel_pct 50 is below min 98",
    ]


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_reading_is_no_go(bad):
    for field in NOMINAL:
        verdict, violations = evaluate_limits(**readings(**{field: bad}))
        assert verdict == "no_go"
        assert len(violations) == 1 and violations[0].startswith(field)


@pytest.mark.parametrize(
    "severity, violations, expected",
    [
        ("high", [], 5),
        ("medium", [], 15),
        ("low", [], 30),
        ("medium", ["wind_knots 30 exceeds max 25"], 5),
        ("low", ["temp_c 1 is below min 4"], 5),
        ("unknown", [], 5),
        ("", [], 5),
        ("LOW", [], 30),
    ],
    ids=["high", "medium", "low", "medium+violation", "low+violation", "unknown", "empty", "case"],
)
def test_brief_by_minutes(severity, violations, expected):
    assert brief_by_minutes(severity, violations) == expected


def test_rules_module_has_no_llm_import():
    source = Path(rules.__file__).read_text()
    imported = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            imported.append(module)
            if module == "app":  # catches `from app import llm`
                imported += [f"app.{alias.name}" for alias in node.names]
    forbidden = [
        name for name in imported
        if name == "openai" or name.startswith("openai.")
        or name == "app.llm" or name.startswith("app.llm.")
    ]
    assert forbidden == [], f"app/rules.py must not import model code: {forbidden}"
    # No dynamic imports either (importlib / __import__) that could pull model code in.
    assert "importlib" not in imported
    calls = [
        n.func.id for n in ast.walk(ast.parse(source))
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
    ]
    assert "__import__" not in calls

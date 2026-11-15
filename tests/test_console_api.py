import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.cost import report_cost, step_cost
from app.llm.fake import FakeLLMClient
from app.main import create_app, get_llm_client

STATIC = Path(__file__).resolve().parent.parent / "static"

REPORT = {
    "name": "Ada",
    "station": "Pad 39",
    "wind_knots": 30,
    "temp_c": 15,
    "fuel_pct": 99,
    "note": "Valve 3 slow to close at T-40, about 4 seconds late.",
}

CODE_STEPS = {"limits", "brief_by"}
MODEL_STEPS = ["classify", "check_injection", "check_missing", "check_panic"]
STEP_FIELDS = {"name", "input_tokens", "output_tokens", "cost_usd", "duration_ms", "summary"}


def make_client(tmp_path, monkeypatch, fake_factory=FakeLLMClient):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    app = create_app()
    app.dependency_overrides[get_llm_client] = lambda: fake_factory()
    return TestClient(app)


@pytest.fixture
def api(tmp_path, monkeypatch):
    # Reviewer rejects once, so the trace has two draft/review rounds.
    return make_client(tmp_path, monkeypatch, lambda: FakeLLMClient(replies={
        "review": [{"approved": False, "feedback": "Lead with the verdict."}],
    }))


def test_detail_has_one_trace_step_per_pipeline_step(api):
    report_id = api.post("/api/reports", json=REPORT).json()["id"]
    r = api.get(f"/api/reports/{report_id}")
    assert r.status_code == 200
    detail = r.json()

    names = [s["name"] for s in detail["steps"]]
    assert names == ["limits", "classify", "brief_by", *MODEL_STEPS[1:],
                     "draft_1", "review_1", "draft_2", "review_2"]
    for s in detail["steps"]:
        assert set(s) == STEP_FIELDS
        assert isinstance(s["input_tokens"], int) and isinstance(s["output_tokens"], int)
        if s["name"] in CODE_STEPS:
            assert (s["input_tokens"], s["output_tokens"], s["cost_usd"]) == (0, 0, 0)
        else:
            assert (s["input_tokens"], s["output_tokens"]) == (100, 50)

    # Everything the console needs is on the detail.
    assert detail["verdict"] == "no_go"
    assert detail["violations"] == ["wind_knots 30 exceeds max 25"]
    assert detail["brief_by"] == 5
    assert detail["classification"] == {"subsystem": "propulsion", "severity": "medium", "fallback": False}
    assert set(detail["checks"]) == {"injection", "missing", "panic"}
    assert detail["needs_review"] is False
    assert detail["briefing"]["status"] == "pending"
    assert detail["briefing"]["rounds"] == 2
    for field in REPORT:
        assert detail[field] == REPORT[field]


def test_total_cost_is_sum_of_step_costs(api):
    report_id = api.post("/api/reports", json=REPORT).json()["id"]
    detail = api.get(f"/api/reports/{report_id}").json()
    steps = detail["steps"]
    assert detail["total_cost"] == report_cost(steps)
    assert detail["total_cost"] == round(
        sum(step_cost(s["input_tokens"], s["output_tokens"]) for s in steps), 6)
    model_calls = sum(1 for s in steps if s["name"] not in CODE_STEPS)
    assert detail["total_cost"] == pytest.approx(model_calls * step_cost(100, 50))


def test_list_includes_console_fields(api):
    created = api.post("/api/reports", json=REPORT).json()
    listed = api.get("/api/reports").json()
    assert len(listed) == 1
    item = listed[0]
    assert item == {
        "id": created["id"],
        "name": "Ada",
        "station": "Pad 39",
        "created_at": created["created_at"],
        "verdict": "no_go",
        "severity": "medium",
        "subsystem": "propulsion",
        "brief_by": 5,
        "briefing_status": "pending",
        "needs_review": False,
        "total_cost": created["total_cost"],
    }


def test_list_reflects_approval(api):
    created = api.post("/api/reports", json=REPORT).json()
    api.post(f"/api/briefings/{created['briefing']['id']}/approve", json={"approver_name": "FD"})
    assert api.get("/api/reports").json()[0]["briefing_status"] == "approved"


def test_unknown_report_is_404(api):
    r = api.get("/api/reports/999")
    assert r.status_code == 404
    assert r.json()["errors"][0]["field"] == "report"


def test_post_response_matches_detail(api):
    created = api.post("/api/reports", json=REPORT).json()
    assert api.get(f"/api/reports/{created['id']}").json() == created


def test_app_js_has_no_innerhtml():
    source = (STATIC / "app.js").read_text()
    assert "innerHTML" not in source
    assert "outerHTML" not in source
    assert "insertAdjacentHTML" not in source
    assert not re.search(r"document\.write\s*\(", source)


def test_app_js_does_no_cost_math():
    """Costs are formatted in JS but never computed there (no price constants)."""
    source = (STATIC / "app.js").read_text()
    assert "price" not in source.lower()
    assert not re.search(r"(input|output)_tokens\s*\*", source)


def test_index_has_console_and_form():
    html = (STATIC / "index.html").read_text()
    for field in REPORT:
        assert f'id="{field}"' in html
    assert 'id="reports"' in html and 'id="detail"' in html


def test_trace_card_formats_are_compact():
    """Cards: cost to 4 decimals, time in whole ms. Report total stays at 6."""
    source = (STATIC / "app.js").read_text()
    assert "formatCost(step.cost_usd, 4)" in source
    assert "formatMs(step.duration_ms)" in source
    assert "Math.round" in source
    assert "formatCost(r.total_cost)" in source  # default 6 decimals
    assert "decimals = 6" in source


def test_trace_stat_values_do_not_wrap():
    css = (STATIC / "styles.css").read_text()
    dd_rule = re.search(r"\.trace-stats dd\s*\{([^}]*)\}", css).group(1)
    assert "white-space: nowrap" in dd_rule
    assert "overflow-wrap: anywhere" not in dd_rule

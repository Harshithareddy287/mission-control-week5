import pytest
from fastapi.testclient import TestClient

from app.main import create_app

VALID = {
    "name": "Ada Lovelace",
    "station": "Pad 39A",
    "wind_knots": 12.5,
    "temp_c": 21,
    "fuel_pct": 87,
    "note": "Minor valve chatter on LOX line during chilldown.",
}


@pytest.fixture
def db_file(tmp_path, monkeypatch):
    path = tmp_path / "test.db"
    monkeypatch.setenv("DB_PATH", str(path))
    return path


@pytest.fixture
def client(db_file):
    return TestClient(create_app())


def errors_by_field(response):
    return {e["field"]: e["message"] for e in response.json()["errors"]}


def test_post_report_all_fields_saved(client):
    payload = {**VALID, "name": "  Ada Lovelace  "}
    r = client.post("/api/reports", json=payload)
    assert r.status_code == 201
    created = r.json()
    assert isinstance(created["id"], int)
    assert created["created_at"]
    assert created["name"] == "Ada Lovelace"  # stripped
    for key in ("station", "wind_knots", "temp_c", "fuel_pct", "note"):
        assert created[key] == VALID[key]

    listed = client.get("/api/reports").json()
    assert listed == [created]


def test_bad_input_rejected_with_message(client):
    # Missing name
    bad = {k: v for k, v in VALID.items() if k != "name"}
    r = client.post("/api/reports", json=bad)
    assert r.status_code == 422
    assert errors_by_field(r) == {"name": "Name is required."}

    # Text in wind_knots
    r = client.post("/api/reports", json={**VALID, "wind_knots": "gusty"})
    assert r.status_code == 422
    assert errors_by_field(r) == {"wind_knots": "Wind (knots) must be a number."}

    # fuel_pct out of range
    r = client.post("/api/reports", json={**VALID, "fuel_pct": 150})
    assert r.status_code == 422
    assert errors_by_field(r) == {"fuel_pct": "Fuel (%) must be between 0 and 100."}

    # All three at once are reported per field
    r = client.post(
        "/api/reports", json={**bad, "wind_knots": "gusty", "fuel_pct": 150}
    )
    assert r.status_code == 422
    assert set(errors_by_field(r)) == {"name", "wind_knots", "fuel_pct"}

    # Nothing bad was saved
    assert client.get("/api/reports").json() == []


def test_blank_and_too_long_text_rejected(client):
    r = client.post("/api/reports", json={**VALID, "station": "   "})
    assert errors_by_field(r) == {"station": "Station cannot be empty."}

    r = client.post("/api/reports", json={**VALID, "note": "x" * 2001})
    assert errors_by_field(r) == {"note": "Note must be at most 2000 characters."}


def test_malformed_body_rejected(client):
    r = client.post(
        "/api/reports", content="not json", headers={"content-type": "application/json"}
    )
    assert r.status_code == 422
    assert errors_by_field(r) == {"body": "Request body is not valid JSON."}


def test_reports_listed_newest_first(client):
    first = client.post("/api/reports", json={**VALID, "note": "first"}).json()
    second = client.post("/api/reports", json={**VALID, "note": "second"}).json()
    assert [r["id"] for r in client.get("/api/reports").json()] == [second["id"], first["id"]]


def test_reports_survive_restart(db_file):
    app1 = create_app()
    created = TestClient(app1).post("/api/reports", json=VALID).json()
    del app1

    app2 = create_app()
    listed = TestClient(app2).get("/api/reports").json()
    assert listed == [created]
    assert db_file.exists()

"""SQLite storage for reports and their pipeline results (plain sqlite3)."""
import json
import os
import sqlite3
from datetime import datetime, timezone

DEFAULT_DB_PATH = "mission_control.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS reports (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT    NOT NULL,
    station    TEXT    NOT NULL,
    wind_knots REAL    NOT NULL,
    temp_c     REAL    NOT NULL,
    fuel_pct   REAL    NOT NULL,
    note       TEXT    NOT NULL,
    created_at TEXT    NOT NULL
);

-- Separate table (not new columns on reports) so existing databases keep working:
-- CREATE TABLE IF NOT EXISTS never adds columns to an existing table.
CREATE TABLE IF NOT EXISTS report_results (
    report_id               INTEGER PRIMARY KEY REFERENCES reports(id),
    verdict                 TEXT    NOT NULL CHECK (verdict IN ('go', 'no_go')),
    violations              TEXT    NOT NULL,  -- JSON list of strings
    subsystem               TEXT    NOT NULL,
    severity                TEXT    NOT NULL,
    classification_fallback INTEGER NOT NULL,
    brief_by                INTEGER NOT NULL,
    checks                  TEXT    NOT NULL,  -- JSON {injection|missing|panic: {flag, reason}}
    needs_review            INTEGER NOT NULL,
    total_cost              REAL    NOT NULL
);

CREATE TABLE IF NOT EXISTS steps (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id     INTEGER NOT NULL REFERENCES reports(id),
    name          TEXT    NOT NULL,
    input_tokens  INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    cost_usd      REAL    NOT NULL,
    duration_ms   REAL    NOT NULL,
    summary       TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS steps_report_id ON steps(report_id);
"""

REPORT_COLUMNS = ("id", "name", "station", "wind_knots", "temp_c", "fuel_pct", "note", "created_at")
STEP_COLUMNS = ("name", "input_tokens", "output_tokens", "cost_usd", "duration_ms", "summary")

EMPTY_RESULTS = {
    "verdict": None,
    "violations": [],
    "subsystem": None,
    "severity": None,
    "classification_fallback": None,
    "brief_by": None,
    "checks": None,
    "needs_review": None,
    "total_cost": None,
    "steps": [],
}


def db_path_from_env() -> str:
    return os.environ.get("DB_PATH") or DEFAULT_DB_PATH


def connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(path: str) -> None:
    conn = connect(path)
    try:
        conn.executescript(SCHEMA)
    finally:
        conn.close()


def insert_report(path: str, data: dict) -> int:
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    conn = connect(path)
    try:
        with conn:
            cur = conn.execute(
                "INSERT INTO reports (name, station, wind_knots, temp_c, fuel_pct, note, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    data["name"],
                    data["station"],
                    data["wind_knots"],
                    data["temp_c"],
                    data["fuel_pct"],
                    data["note"],
                    created_at,
                ),
            )
        return cur.lastrowid
    finally:
        conn.close()


def save_results(path: str, report_id: int, results: dict) -> None:
    """Store pipeline results and trace steps for a report in one transaction."""
    conn = connect(path)
    try:
        with conn:
            conn.execute(
                "INSERT INTO report_results (report_id, verdict, violations, subsystem, severity,"
                " classification_fallback, brief_by, checks, needs_review, total_cost)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    report_id,
                    results["verdict"],
                    json.dumps(results["violations"]),
                    results["subsystem"],
                    results["severity"],
                    int(results["classification_fallback"]),
                    results["brief_by"],
                    json.dumps(results["checks"]),
                    int(results["needs_review"]),
                    results["total_cost"],
                ),
            )
            conn.executemany(
                f"INSERT INTO steps (report_id, {', '.join(STEP_COLUMNS)})"
                f" VALUES (?, {', '.join('?' * len(STEP_COLUMNS))})",
                [(report_id, *(s[c] for c in STEP_COLUMNS)) for s in results["steps"]],
            )
    finally:
        conn.close()


def _results_from_row(row: sqlite3.Row) -> dict:
    return {
        "verdict": row["verdict"],
        "violations": json.loads(row["violations"]),
        "subsystem": row["subsystem"],
        "severity": row["severity"],
        "classification_fallback": bool(row["classification_fallback"]),
        "brief_by": row["brief_by"],
        "checks": json.loads(row["checks"]),
        "needs_review": bool(row["needs_review"]),
        "total_cost": row["total_cost"],
    }


def _load(conn: sqlite3.Connection, where: str = "", params: tuple = ()) -> list[dict]:
    cols = ", ".join(f"r.{c}" for c in REPORT_COLUMNS)
    rows = conn.execute(
        f"SELECT {cols}, rr.* FROM reports r"
        f" LEFT JOIN report_results rr ON rr.report_id = r.id {where}"
        " ORDER BY r.id DESC",
        params,
    ).fetchall()
    if not rows:
        return []

    ids = [row["id"] for row in rows]
    steps: dict[int, list[dict]] = {i: [] for i in ids}
    for s in conn.execute(
        f"SELECT report_id, {', '.join(STEP_COLUMNS)} FROM steps"
        f" WHERE report_id IN ({', '.join('?' * len(ids))}) ORDER BY id",
        ids,
    ):
        steps[s["report_id"]].append({c: s[c] for c in STEP_COLUMNS})

    reports = []
    for row in rows:
        report = {c: row[c] for c in REPORT_COLUMNS}
        if row["report_id"] is None:  # filed but pipeline results not saved
            report.update(EMPTY_RESULTS, steps=[])
        else:
            report.update(_results_from_row(row), steps=steps[row["id"]])
        reports.append(report)
    return reports


def get_report(path: str, report_id: int) -> dict | None:
    conn = connect(path)
    try:
        found = _load(conn, "WHERE r.id = ?", (report_id,))
        return found[0] if found else None
    finally:
        conn.close()


def list_reports(path: str) -> list[dict]:
    conn = connect(path)
    try:
        return _load(conn)
    finally:
        conn.close()

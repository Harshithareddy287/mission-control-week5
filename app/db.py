"""SQLite storage for reports (plain sqlite3, one connection per operation)."""
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
)
"""

COLUMNS = ("id", "name", "station", "wind_knots", "temp_c", "fuel_pct", "note", "created_at")


def db_path_from_env() -> str:
    return os.environ.get("DB_PATH") or DEFAULT_DB_PATH


def connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(path: str) -> None:
    with connect(path) as conn:
        conn.execute(SCHEMA)
    conn.close()


def insert_report(path: str, data: dict) -> dict:
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
        row = conn.execute(
            f"SELECT {', '.join(COLUMNS)} FROM reports WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
        return dict(row)
    finally:
        conn.close()


def list_reports(path: str) -> list[dict]:
    conn = connect(path)
    try:
        rows = conn.execute(
            f"SELECT {', '.join(COLUMNS)} FROM reports ORDER BY id DESC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

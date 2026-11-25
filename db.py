"""
db.py – SQLite persistence layer for naukri-assistant
======================================================
Tables
------
applied_jobs  – every job we successfully applied to
skipped_jobs  – every job we decided to skip (with reason)
runs          – one row per script invocation (boost / apply / both)
"""

from __future__ import annotations

import csv
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent / "naukri_assistant.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    """Create tables if they don't exist yet."""
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS applied_jobs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id      TEXT    NOT NULL UNIQUE,
                title       TEXT,
                company     TEXT,
                location    TEXT,
                url         TEXT,
                applied_at  TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS skipped_jobs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id      TEXT    NOT NULL,
                title       TEXT,
                company     TEXT,
                url         TEXT,
                reason      TEXT,
                skipped_at  TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS runs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                mode        TEXT    NOT NULL,
                started_at  TEXT    NOT NULL,
                ended_at    TEXT,
                applied     INTEGER DEFAULT 0,
                skipped     INTEGER DEFAULT 0,
                status      TEXT    DEFAULT 'running',
                notes       TEXT
            );
            """
        )


def run_start(mode: str) -> int:
    """Insert a new run row and return its id."""
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO runs (mode, started_at) VALUES (?, ?)",
            (mode, _now()),
        )
        return cur.lastrowid  # type: ignore[return-value]


def run_end(run_id: int, applied: int, skipped: int, status: str = "ok", notes: str = "") -> None:
    """Update run row on completion."""
    with _connect() as conn:
        conn.execute(
            "UPDATE runs SET ended_at=?, applied=?, skipped=?, status=?, notes=? WHERE id=?",
            (_now(), applied, skipped, status, notes, run_id),
        )


def already_applied(job_id: str) -> bool:
    """Return True if the job_id exists in applied_jobs."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM applied_jobs WHERE job_id=?", (job_id,)
        ).fetchone()
        return row is not None


def record_applied(
    job_id: str, title: str, company: str, location: str, url: str
) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO applied_jobs
                (job_id, title, company, location, url, applied_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (job_id, title, company, location, url, _now()),
        )


def record_skipped(
    job_id: str, title: str, company: str, url: str, reason: str
) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO skipped_jobs
                (job_id, title, company, url, reason, skipped_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (job_id, title, company, url, reason, _now()),
        )


def applications_today() -> int:
    """Count applications submitted today (calendar day)."""
    today = date.today().isoformat()
    with _connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM applied_jobs WHERE applied_at LIKE ?",
            (f"{today}%",),
        ).fetchone()
        return row[0]


def export_csv(out_path: Optional[Path] = None) -> Path:
    """
    Export applied_jobs and skipped_jobs to a combined CSV.
    Returns the path of the written file.
    """
    if out_path is None:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = Path(__file__).parent / f"report_{stamp}.csv"

    with _connect() as conn:
        applied = conn.execute(
            "SELECT 'applied' AS status, job_id, title, company, location, url, applied_at AS ts"
            " FROM applied_jobs ORDER BY applied_at DESC"
        ).fetchall()
        skipped = conn.execute(
            "SELECT 'skipped' AS status, job_id, title, company, '' AS location, url, skipped_at AS ts"
            " FROM skipped_jobs ORDER BY skipped_at DESC"
        ).fetchall()

    rows = list(applied) + list(skipped)
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["status", "job_id", "title", "company", "location", "url", "timestamp"])
        for row in rows:
            writer.writerow(list(row))

    return out_path


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")

"""SQLite database setup and project storage.

Table: projects
- id (integer, primary key)
- url (text)
- result_json (text)
- created_at (datetime)
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "seomentor.db"


def get_connection() -> sqlite3.Connection:
    """Return a connection to the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create the projects table if it does not exist."""
    conn = get_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL,
                result_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def insert_project(url: str, result_json: dict) -> int:
    """Store a new project and return its id."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            "INSERT INTO projects (url, result_json, created_at) VALUES (?, ?, ?)",
            (url, json.dumps(result_json), datetime.utcnow().isoformat()),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_project(project_id: int) -> dict | None:
    """Fetch a project by id. Returns parsed result_json or None."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT url, result_json, created_at FROM projects WHERE id = ?",
            (project_id,),
        ).fetchone()
        if row is None:
            return None
        return {
            "url": row["url"],
            "result_json": json.loads(row["result_json"]),
            "created_at": row["created_at"],
        }
    finally:
        conn.close()


def update_project_result(project_id: int, result_json: dict) -> None:
    """Update stored result_json for a project."""
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE projects SET result_json = ? WHERE id = ?",
            (json.dumps(result_json), project_id),
        )
        conn.commit()
    finally:
        conn.close()


def list_projects(limit: int = 20) -> list[dict]:
    """Return recent projects for history view."""
    safe_limit = max(1, min(100, int(limit)))
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT id, url, result_json, created_at
            FROM projects
            ORDER BY id DESC
            LIMIT ?
            """,
            (safe_limit,),
        ).fetchall()

        out: list[dict] = []
        for row in rows:
            try:
                parsed = json.loads(row["result_json"])
            except Exception:
                parsed = {}

            roadmap = parsed.get("roadmap", [])
            plan_days = len(roadmap) if isinstance(roadmap, list) else 0
            score = parsed.get("seo_score", 0)
            try:
                score_num = float(score)
            except (TypeError, ValueError):
                score_num = 0.0

            out.append(
                {
                    "id": row["id"],
                    "url": row["url"],
                    "seo_score": score_num,
                    "plan_days": plan_days,
                    "created_at": row["created_at"],
                }
            )
        return out
    finally:
        conn.close()

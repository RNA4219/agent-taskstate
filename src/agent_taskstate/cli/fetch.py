"""
CLI Fetch Helpers
"""

from __future__ import annotations

import sqlite3
from typing import Any, Sequence

from .errors import NotFoundError


def fetch_one(conn: sqlite3.Connection, sql: str, params: Sequence[Any]) -> sqlite3.Row:
    """Fetch one row or raise NotFoundError."""
    row = conn.execute(sql, params).fetchone()
    if row is None:
        raise NotFoundError("resource not found")
    return row


def get_task(conn: sqlite3.Connection, task_id: str) -> sqlite3.Row:
    """Get task by ID."""
    return fetch_one(conn, "SELECT * FROM tasks WHERE id = ?", (task_id,))


def get_task_state(conn: sqlite3.Connection, task_id: str) -> sqlite3.Row:
    """Get task_state by task_id."""
    return fetch_one(conn, "SELECT * FROM task_states WHERE task_id = ?", (task_id,))


def get_decision(conn: sqlite3.Connection, decision_id: str) -> sqlite3.Row:
    """Get decision by ID."""
    return fetch_one(conn, "SELECT * FROM decisions WHERE id = ?", (decision_id,))


def get_question(conn: sqlite3.Connection, question_id: str) -> sqlite3.Row:
    """Get question by ID."""
    return fetch_one(conn, "SELECT * FROM open_questions WHERE id = ?", (question_id,))


def get_run(conn: sqlite3.Connection, run_id: str) -> sqlite3.Row:
    """Get run by ID."""
    return fetch_one(conn, "SELECT * FROM runs WHERE id = ?", (run_id,))


def get_bundle(conn: sqlite3.Connection, bundle_id: str) -> sqlite3.Row:
    """Get context_bundle by ID."""
    return fetch_one(conn, "SELECT * FROM context_bundles WHERE id = ?", (bundle_id,))

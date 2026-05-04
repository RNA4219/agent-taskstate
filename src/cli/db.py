"""
CLI Database Connection and Schema
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable

from .constants import TASK_PHASE2_COLUMNS


def ensure_parent_dir(path: str) -> None:
    """Ensure parent directory exists."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)


@contextmanager
def connect(db_path: str) -> Iterable[sqlite3.Connection]:
    """Connect to SQLite database with transaction management."""
    ensure_parent_dir(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS tasks (
  id TEXT PRIMARY KEY,
  parent_task_id TEXT,
  kind TEXT NOT NULL,
  title TEXT NOT NULL,
  goal TEXT NOT NULL,
  status TEXT NOT NULL,
  priority TEXT NOT NULL,
  owner_type TEXT NOT NULL,
  owner_id TEXT,
  idempotency_key TEXT,
  note_id TEXT,
  trace_id TEXT,
  reply_target TEXT,
  reply_state TEXT,
  retry_count INTEGER NOT NULL DEFAULT 0,
  kestra_execution_id TEXT,
  original_task_id TEXT,
  trigger TEXT,
  reply_text TEXT,
  roadmap_request_json TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(parent_task_id) REFERENCES tasks(id)
);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_kind ON tasks(kind);
CREATE INDEX IF NOT EXISTS idx_tasks_owner ON tasks(owner_type, owner_id);

CREATE TABLE IF NOT EXISTS task_states (
  task_id TEXT PRIMARY KEY,
  revision INTEGER NOT NULL,
  current_step TEXT NOT NULL,
  constraints_json TEXT NOT NULL,
  done_when_json TEXT NOT NULL,
  current_summary TEXT,
  artifact_refs_json TEXT NOT NULL,
  evidence_refs_json TEXT NOT NULL,
  confidence TEXT,
  context_policy_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS decisions (
  id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL,
  summary TEXT NOT NULL,
  rationale TEXT,
  status TEXT NOT NULL,
  confidence TEXT,
  evidence_refs_json TEXT NOT NULL,
  supersedes_decision_id TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE,
  FOREIGN KEY(supersedes_decision_id) REFERENCES decisions(id)
);
CREATE INDEX IF NOT EXISTS idx_decisions_task ON decisions(task_id);
CREATE INDEX IF NOT EXISTS idx_decisions_task_status ON decisions(task_id, status);

CREATE TABLE IF NOT EXISTS open_questions (
  id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL,
  question TEXT NOT NULL,
  priority TEXT NOT NULL,
  status TEXT NOT NULL,
  answer TEXT,
  evidence_refs_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_open_questions_task ON open_questions(task_id);
CREATE INDEX IF NOT EXISTS idx_open_questions_task_status ON open_questions(task_id, status);

CREATE TABLE IF NOT EXISTS runs (
  id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL,
  actor_type TEXT NOT NULL,
  actor_id TEXT,
  run_type TEXT NOT NULL,
  status TEXT NOT NULL,
  input_ref TEXT,
  output_ref TEXT,
  started_at TEXT NOT NULL,
  ended_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_runs_task ON runs(task_id);

CREATE TABLE IF NOT EXISTS context_bundles (
  id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL,
  build_reason TEXT NOT NULL,
  state_snapshot_json TEXT NOT NULL,
  included_decision_refs_json TEXT NOT NULL,
  included_open_question_refs_json TEXT NOT NULL,
  included_artifact_refs_json TEXT NOT NULL,
  included_evidence_refs_json TEXT NOT NULL,
  expected_output_schema_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  metadata_json TEXT,
  FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_context_bundles_task ON context_bundles(task_id);
"""


def _task_column_names(conn: sqlite3.Connection) -> set[str]:
    """Get existing task table column names."""
    rows = conn.execute("PRAGMA table_info(tasks)").fetchall()
    return {row["name"] for row in rows}


def _ensure_task_phase2_columns(conn: sqlite3.Connection) -> None:
    """Ensure Phase2 columns exist in tasks table."""
    columns = _task_column_names(conn)
    for name, ddl in TASK_PHASE2_COLUMNS.items():
        if name not in columns:
            conn.execute(f"ALTER TABLE tasks ADD COLUMN {name} {ddl}")
    conn.execute("UPDATE tasks SET retry_count = 0 WHERE retry_count IS NULL")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_updated_at ON tasks(updated_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_idempotency_key ON tasks(idempotency_key)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_trace_id ON tasks(trace_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_reply_state ON tasks(reply_state)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_original_task_id ON tasks(original_task_id)")


def init_db(conn: sqlite3.Connection) -> None:
    """Initialize database schema."""
    conn.executescript(SCHEMA_SQL)
    _ensure_task_phase2_columns(conn)
"""SQLite connection and the plural agent-taskstate schema."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable

from .constants import TASK_PHASE2_COLUMNS


def ensure_parent_dir(path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)


@contextmanager
def connect(db_path: str) -> Iterable[sqlite3.Connection]:
    ensure_parent_dir(db_path)
    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 30000")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (
  version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tasks (
  id TEXT PRIMARY KEY, parent_task_id TEXT, kind TEXT NOT NULL, title TEXT NOT NULL,
  goal TEXT NOT NULL, status TEXT NOT NULL, priority TEXT NOT NULL,
  owner_type TEXT NOT NULL, owner_id TEXT, tracker_issue_ref TEXT,
  idempotency_key TEXT, note_id TEXT, trace_id TEXT, reply_target TEXT,
  reply_state TEXT, retry_count INTEGER NOT NULL DEFAULT 0,
  kestra_execution_id TEXT, original_task_id TEXT, trigger TEXT, reply_text TEXT,
  roadmap_request_json TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  FOREIGN KEY(parent_task_id) REFERENCES tasks(id)
);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_kind ON tasks(kind);
CREATE INDEX IF NOT EXISTS idx_tasks_owner ON tasks(owner_type, owner_id);
CREATE TABLE IF NOT EXISTS task_states (
  task_id TEXT PRIMARY KEY, revision INTEGER NOT NULL, current_step TEXT NOT NULL,
  constraints_json TEXT NOT NULL, done_when_json TEXT NOT NULL, current_summary TEXT,
  artifact_refs_json TEXT NOT NULL, evidence_refs_json TEXT NOT NULL, confidence TEXT,
  context_policy_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS decisions (
  id TEXT PRIMARY KEY, task_id TEXT NOT NULL, summary TEXT NOT NULL, rationale TEXT,
  status TEXT NOT NULL, confidence TEXT, evidence_refs_json TEXT NOT NULL,
  supersedes_decision_id TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE,
  FOREIGN KEY(supersedes_decision_id) REFERENCES decisions(id)
);
CREATE INDEX IF NOT EXISTS idx_decisions_task ON decisions(task_id);
CREATE TABLE IF NOT EXISTS open_questions (
  id TEXT PRIMARY KEY, task_id TEXT NOT NULL, question TEXT NOT NULL,
  priority TEXT NOT NULL, status TEXT NOT NULL, answer TEXT,
  evidence_refs_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_open_questions_task ON open_questions(task_id);
CREATE TABLE IF NOT EXISTS runs (
  id TEXT PRIMARY KEY, task_id TEXT NOT NULL, actor_type TEXT NOT NULL, actor_id TEXT,
  run_type TEXT NOT NULL, status TEXT NOT NULL, input_ref TEXT, output_ref TEXT,
  started_at TEXT NOT NULL, ended_at TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_runs_task ON runs(task_id);
CREATE TABLE IF NOT EXISTS context_bundles (
  id TEXT PRIMARY KEY, task_id TEXT NOT NULL, build_reason TEXT NOT NULL,
  state_snapshot_json TEXT NOT NULL, included_decision_refs_json TEXT NOT NULL,
  included_open_question_refs_json TEXT NOT NULL, included_artifact_refs_json TEXT NOT NULL,
  included_evidence_refs_json TEXT NOT NULL, expected_output_schema_json TEXT NOT NULL,
  created_at TEXT NOT NULL, metadata_json TEXT,
  purpose TEXT NOT NULL DEFAULT 'continue_work', rebuild_level TEXT NOT NULL DEFAULT 'L2',
  summary TEXT, decision_digest_json TEXT, question_digest_json TEXT, diagnostics_json TEXT,
  raw_included INTEGER NOT NULL DEFAULT 0, generator_version TEXT NOT NULL DEFAULT '1.1.0',
  generated_at TEXT, state_snapshot_compressed INTEGER NOT NULL DEFAULT 0,
  decision_digest_compressed INTEGER NOT NULL DEFAULT 0,
  question_digest_compressed INTEGER NOT NULL DEFAULT 0,
  diagnostics_compressed INTEGER NOT NULL DEFAULT 0,
  FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_context_bundles_task ON context_bundles(task_id);
CREATE TABLE IF NOT EXISTS context_bundle_sources (
  id TEXT PRIMARY KEY, context_bundle_id TEXT NOT NULL, typed_ref TEXT NOT NULL,
  source_kind TEXT NOT NULL, selected_raw INTEGER NOT NULL DEFAULT 0,
  metadata_json TEXT, created_at TEXT NOT NULL,
  FOREIGN KEY(context_bundle_id) REFERENCES context_bundles(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_context_bundle_sources_bundle ON context_bundle_sources(context_bundle_id);
CREATE TABLE IF NOT EXISTS state_transitions (
  id TEXT PRIMARY KEY, task_id TEXT NOT NULL, from_status TEXT, to_status TEXT NOT NULL,
  reason TEXT NOT NULL DEFAULT '', actor_type TEXT NOT NULL, actor_id TEXT, run_id TEXT,
  changed_at TEXT NOT NULL, FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_state_transitions_task_changed
  ON state_transitions(task_id, changed_at ASC, id ASC);
CREATE TABLE IF NOT EXISTS tracker_connection (
  id TEXT PRIMARY KEY, provider TEXT NOT NULL, name TEXT NOT NULL, config_json TEXT NOT NULL,
  secret_env_json TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS issue_cache (
  id TEXT PRIMARY KEY, connection_id TEXT NOT NULL, issue_ref TEXT NOT NULL UNIQUE,
  remote_key TEXT NOT NULL, title TEXT NOT NULL, status TEXT NOT NULL, assignee TEXT,
  description TEXT, labels_json TEXT, raw_json TEXT, fetched_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  FOREIGN KEY(connection_id) REFERENCES tracker_connection(id)
);
CREATE TABLE IF NOT EXISTS entity_link (
  id TEXT PRIMARY KEY, tracker_issue_ref TEXT NOT NULL,
  agent_taskstate_entity_ref TEXT NOT NULL, role TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sync_event (
  id TEXT PRIMARY KEY, connection_id TEXT NOT NULL, direction TEXT NOT NULL,
  status TEXT NOT NULL, issue_ref TEXT, details_json TEXT, error_message TEXT,
  created_at TEXT NOT NULL, FOREIGN KEY(connection_id) REFERENCES tracker_connection(id)
);
"""


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}


def _ensure_task_phase2_columns(conn: sqlite3.Connection) -> None:
    columns = _columns(conn, "tasks")
    for name, ddl in {**TASK_PHASE2_COLUMNS, "tracker_issue_ref": "TEXT"}.items():
        if name not in columns:
            conn.execute(f"ALTER TABLE tasks ADD COLUMN {name} {ddl}")
    conn.execute("UPDATE tasks SET retry_count = 0 WHERE retry_count IS NULL")
    for sql in (
        "CREATE INDEX IF NOT EXISTS idx_tasks_updated_at ON tasks(updated_at)",
        "CREATE INDEX IF NOT EXISTS idx_tasks_idempotency_key ON tasks(idempotency_key)",
        "CREATE INDEX IF NOT EXISTS idx_tasks_trace_id ON tasks(trace_id)",
        "CREATE INDEX IF NOT EXISTS idx_tasks_reply_state ON tasks(reply_state)",
        "CREATE INDEX IF NOT EXISTS idx_tasks_original_task_id ON tasks(original_task_id)",
        "CREATE INDEX IF NOT EXISTS idx_tasks_tracker_issue_ref ON tasks(tracker_issue_ref)",
    ):
        conn.execute(sql)


def init_db(conn: sqlite3.Connection) -> None:
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_SQL)
    _ensure_task_phase2_columns(conn)
    from ..migrations import run_migrations

    run_migrations(conn)

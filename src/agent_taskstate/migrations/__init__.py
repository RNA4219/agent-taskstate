"""Idempotent migrations for the plural 1.1.0 database."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Callable

from ..typed_ref import canonicalize_ref

CURRENT_SCHEMA_VERSION = 2


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}


def _add_column(conn: sqlite3.Connection, table: str, name: str, ddl: str) -> None:
    if name not in _columns(conn, table):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")


def _migration_001(conn: sqlite3.Connection) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO schema_version(version, name, applied_at) VALUES (1, ?, ?)",
        ("plural-1.0.1", _now()),
    )


def _migration_002(conn: sqlite3.Connection) -> None:
    """Add history, bundle audit columns, and backfill legacy plural data."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS state_transitions (
          id TEXT PRIMARY KEY, task_id TEXT NOT NULL, from_status TEXT,
          to_status TEXT NOT NULL, reason TEXT NOT NULL DEFAULT '',
          actor_type TEXT NOT NULL, actor_id TEXT, run_id TEXT,
          changed_at TEXT NOT NULL,
          FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_state_transitions_task_changed "
        "ON state_transitions(task_id, changed_at ASC, id ASC)"
    )
    if "secret_env_json" not in _columns(conn, "tracker_connection"):
        _add_column(conn, "tracker_connection", "secret_env_json", "TEXT NOT NULL DEFAULT '{}'")
    bundle_columns = {
        "purpose": "TEXT NOT NULL DEFAULT 'continue_work'",
        "rebuild_level": "TEXT NOT NULL DEFAULT 'L2'",
        "summary": "TEXT",
        "decision_digest_json": "TEXT",
        "question_digest_json": "TEXT",
        "diagnostics_json": "TEXT",
        "raw_included": "INTEGER NOT NULL DEFAULT 0",
        "generator_version": "TEXT NOT NULL DEFAULT 'legacy/1.0.1'",
        "generated_at": "TEXT",
        "state_snapshot_compressed": "INTEGER NOT NULL DEFAULT 0",
        "decision_digest_compressed": "INTEGER NOT NULL DEFAULT 0",
        "question_digest_compressed": "INTEGER NOT NULL DEFAULT 0",
        "diagnostics_compressed": "INTEGER NOT NULL DEFAULT 0",
    }
    for name, ddl in bundle_columns.items():
        _add_column(conn, "context_bundles", name, ddl)
    conn.execute("UPDATE context_bundles SET generated_at = created_at WHERE generated_at IS NULL")
    conn.execute(
        """
        UPDATE context_bundles
        SET purpose = CASE build_reason
          WHEN 'review' THEN 'review_prepare'
          WHEN 'recovery' THEN 'resume_after_block'
          WHEN 'ambiguity' THEN 'decision_support'
          WHEN 'high_risk' THEN 'decision_support'
          ELSE 'continue_work'
        END,
        rebuild_level = 'L1', generator_version = 'legacy/1.0.1',
        diagnostics_json = COALESCE(diagnostics_json, ?), raw_included = COALESCE(raw_included, 0)
        WHERE diagnostics_json IS NULL
        """,
        (json.dumps({"legacy_backfill": True}, ensure_ascii=False),),
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS context_bundle_sources (
          id TEXT PRIMARY KEY, context_bundle_id TEXT NOT NULL,
          typed_ref TEXT NOT NULL, source_kind TEXT NOT NULL,
          selected_raw INTEGER NOT NULL DEFAULT 0, metadata_json TEXT,
          created_at TEXT NOT NULL,
          FOREIGN KEY(context_bundle_id) REFERENCES context_bundles(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_context_bundle_sources_bundle "
        "ON context_bundle_sources(context_bundle_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_context_bundle_sources_ref "
        "ON context_bundle_sources(typed_ref)"
    )

    rows = conn.execute(
        """
        SELECT id, created_at, included_decision_refs_json,
               included_open_question_refs_json, included_artifact_refs_json,
               included_evidence_refs_json
        FROM context_bundles
        """
    ).fetchall()
    for row in rows:
        for kind, encoded in (
            ("decision", row["included_decision_refs_json"]),
            ("open_question", row["included_open_question_refs_json"]),
            ("artifact", row["included_artifact_refs_json"]),
            ("evidence", row["included_evidence_refs_json"]),
        ):
            try:
                refs = json.loads(encoded or "[]")
            except (TypeError, json.JSONDecodeError):
                refs = []
            for raw_ref in refs:
                try:
                    ref = canonicalize_ref(str(raw_ref))
                except ValueError:
                    continue
                if conn.execute(
                    "SELECT 1 FROM context_bundle_sources WHERE context_bundle_id = ? AND typed_ref = ?",
                    (row["id"], ref),
                ).fetchone():
                    continue
                conn.execute(
                    """
                    INSERT INTO context_bundle_sources
                      (id, context_bundle_id, typed_ref, source_kind, selected_raw, metadata_json, created_at)
                    VALUES (lower(hex(randomblob(16))), ?, ?, ?, 0, ?, ?)
                    """,
                    (
                        row["id"],
                        ref,
                        kind,
                        json.dumps({"legacy_backfill": True}),
                        row["created_at"],
                    ),
                )

    conn.execute(
        """
        INSERT INTO state_transitions
          (id, task_id, from_status, to_status, reason, actor_type, changed_at)
        SELECT lower(hex(randomblob(16))), t.id, NULL, t.status,
               'legacy_backfill', 'system', COALESCE(t.created_at, t.updated_at)
        FROM tasks AS t
        WHERE NOT EXISTS (
          SELECT 1 FROM state_transitions AS h
          WHERE h.task_id = t.id AND h.from_status IS NULL
            AND h.to_status = t.status AND h.actor_type = 'system'
            AND h.reason = 'legacy_backfill'
        )
        """
    )
    conn.execute(
        "INSERT OR IGNORE INTO schema_version(version, name, applied_at) VALUES (2, ?, ?)",
        ("state-history-bundle-audit-1.1.0", _now()),
    )


def run_migrations(conn: sqlite3.Connection) -> None:
    """Run migrations in a transaction and make reruns harmless."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_version (
          version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at TEXT NOT NULL
        )
        """
    )
    own_transaction = not conn.in_transaction
    savepoint = "agent_taskstate_migrations"
    if own_transaction:
        conn.execute("BEGIN")
    else:
        conn.execute(f"SAVEPOINT {savepoint}")
    try:
        applied = {int(row[0]) for row in conn.execute("SELECT version FROM schema_version")}
        migrations: list[tuple[int, Callable[[sqlite3.Connection], None]]] = [
            (1, _migration_001),
            (2, _migration_002),
        ]
        for version, migration in migrations:
            if version not in applied:
                migration(conn)
        if own_transaction:
            conn.commit()
        else:
            conn.execute(f"RELEASE SAVEPOINT {savepoint}")
    except Exception:
        if own_transaction:
            conn.rollback()
        else:
            conn.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
            conn.execute(f"RELEASE SAVEPOINT {savepoint}")
        raise


__all__ = ["CURRENT_SCHEMA_VERSION", "run_migrations"]

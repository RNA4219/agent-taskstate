"""
Context Bundle Service

Manages context bundle creation and audit trails.

Key features:
- Bundle generation with source refs tracking
- Audit information (purpose, rebuild_level, generator_version)
- Source refs stored in separate table for auditability
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .typed_ref import canonicalize_ref


@dataclass
class BundleSource:
    """A single source reference in a context bundle."""

    id: str
    context_bundle_id: str
    typed_ref: str
    source_kind: str
    selected_raw: bool
    metadata_json: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        """Convert source record to dictionary for JSON output."""
        return {
            "id": self.id,
            "context_bundle_id": self.context_bundle_id,
            "typed_ref": self.typed_ref,
            "source_kind": self.source_kind,
            "selected_raw": self.selected_raw,
            "metadata": json.loads(self.metadata_json) if self.metadata_json else None,
        }


@dataclass
class ContextBundle:
    """A context bundle with audit information."""

    id: str
    task_id: str
    purpose: str
    rebuild_level: str
    summary: Optional[str]
    state_snapshot_json: str
    decision_digest_json: Optional[str]
    question_digest_json: Optional[str]
    diagnostics_json: Optional[str]
    raw_included: bool
    generator_version: str
    generated_at: str
    created_at: str
    sources: List[BundleSource] = field(default_factory=list)

    def get_source_refs(self) -> List[str]:
        """Get list of all source refs."""
        return [s.typed_ref for s in self.sources]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON output."""
        return {
            "id": self.id,
            "task_id": self.task_id,
            "purpose": self.purpose,
            "rebuild_level": self.rebuild_level,
            "summary": self.summary,
            "state_snapshot": json.loads(self.state_snapshot_json),
            "decision_digest": json.loads(self.decision_digest_json) if self.decision_digest_json else None,
            "question_digest": json.loads(self.question_digest_json) if self.question_digest_json else None,
            "diagnostics": json.loads(self.diagnostics_json) if self.diagnostics_json else None,
            "raw_included": self.raw_included,
            "generator_version": self.generator_version,
            "generated_at": self.generated_at,
            "created_at": self.created_at,
            "source_refs": self.get_source_refs(),
            "source_count": len(self.sources),
            "sources": [source.to_dict() for source in self.sources],
        }


REBUILD_LEVELS = {"L1", "L2", "L3"}

PURPOSE_TYPES = {
    "continue_work",
    "review_prepare",
    "resume_after_block",
    "decision_support",
    "other",
}

SOURCE_KINDS = {
    "task",
    "decision",
    "open_question",
    "evidence",
    "artifact",
    "run",
    "tracker_issue",
}


def now_utc() -> str:
    """Return current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def gen_id() -> str:
    """Generate a unique ID."""
    import uuid

    return uuid.uuid4().hex


class ContextBundleService:
    """Service for creating and managing context bundles."""

    def __init__(self, conn: sqlite3.Connection, generator_version: str = "1.0.0"):
        self.conn = conn
        self.generator_version = generator_version

    def create_bundle(
        self,
        task_id: str,
        purpose: str,
        rebuild_level: str,
        state_snapshot: Dict[str, Any],
        decision_digest: Optional[Dict[str, Any]] = None,
        question_digest: Optional[Dict[str, Any]] = None,
        diagnostics: Optional[Dict[str, Any]] = None,
        summary: Optional[str] = None,
        raw_included: bool = False,
    ) -> ContextBundle:
        """Create a new context bundle."""
        if purpose not in PURPOSE_TYPES:
            raise ValueError(f"Invalid purpose: {purpose}")
        if rebuild_level not in REBUILD_LEVELS:
            raise ValueError(f"Invalid rebuild_level: {rebuild_level}")

        bundle_id = gen_id()
        now = now_utc()

        self.conn.execute(
            """
            INSERT INTO context_bundle
                (id, task_id, purpose, rebuild_level, summary, state_snapshot_json,
                 decision_digest_json, question_digest_json, diagnostics_json, raw_included,
                 generator_version, generated_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                bundle_id,
                task_id,
                purpose,
                rebuild_level,
                summary,
                json.dumps(state_snapshot),
                json.dumps(decision_digest) if decision_digest else None,
                json.dumps(question_digest) if question_digest else None,
                json.dumps(diagnostics) if diagnostics else None,
                1 if raw_included else 0,
                self.generator_version,
                now,
                now,
            ),
        )

        return ContextBundle(
            id=bundle_id,
            task_id=task_id,
            purpose=purpose,
            rebuild_level=rebuild_level,
            summary=summary,
            state_snapshot_json=json.dumps(state_snapshot),
            decision_digest_json=json.dumps(decision_digest) if decision_digest else None,
            question_digest_json=json.dumps(question_digest) if question_digest else None,
            diagnostics_json=json.dumps(diagnostics) if diagnostics else None,
            raw_included=raw_included,
            generator_version=self.generator_version,
            generated_at=now,
            created_at=now,
        )

    def add_source(
        self,
        bundle_id: str,
        typed_ref: str,
        source_kind: str,
        selected_raw: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> BundleSource:
        """Add a source reference to a bundle."""
        if source_kind not in SOURCE_KINDS:
            raise ValueError(f"Invalid source_kind: {source_kind}")

        canonical_ref = canonicalize_ref(typed_ref)
        source_id = gen_id()
        now = now_utc()

        self.conn.execute(
            """
            INSERT INTO context_bundle_source
                (id, context_bundle_id, typed_ref, source_kind, selected_raw, metadata_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_id,
                bundle_id,
                canonical_ref,
                source_kind,
                1 if selected_raw else 0,
                json.dumps(metadata) if metadata is not None else None,
                now,
            ),
        )

        return BundleSource(
            id=source_id,
            context_bundle_id=bundle_id,
            typed_ref=canonical_ref,
            source_kind=source_kind,
            selected_raw=selected_raw,
            metadata_json=json.dumps(metadata) if metadata is not None else None,
        )

    def get_bundle(self, bundle_id: str) -> Optional[ContextBundle]:
        """Get a context bundle by ID."""
        cursor = self.conn.execute(
            """
            SELECT id, task_id, purpose, rebuild_level, summary, state_snapshot_json,
                   decision_digest_json, question_digest_json, diagnostics_json, raw_included,
                   generator_version, generated_at, created_at
            FROM context_bundle
            WHERE id = ?
            """,
            (bundle_id,),
        )

        row = cursor.fetchone()
        if not row:
            return None

        bundle = ContextBundle(
            id=row[0],
            task_id=row[1],
            purpose=row[2],
            rebuild_level=row[3],
            summary=row[4],
            state_snapshot_json=row[5],
            decision_digest_json=row[6],
            question_digest_json=row[7],
            diagnostics_json=row[8],
            raw_included=bool(row[9]),
            generator_version=row[10],
            generated_at=row[11],
            created_at=row[12],
        )
        bundle.sources = self._load_sources(bundle_id)
        return bundle

    def get_latest_bundle(self, task_id: str) -> Optional[ContextBundle]:
        """Get the latest context bundle for a task."""
        cursor = self.conn.execute(
            """
            SELECT id FROM context_bundle
            WHERE task_id = ?
            ORDER BY generated_at DESC
            LIMIT 1
            """,
            (task_id,),
        )

        row = cursor.fetchone()
        if not row:
            return None

        return self.get_bundle(row[0])

    def list_bundles(self, task_id: str) -> List[ContextBundle]:
        """List all context bundles for a task."""
        cursor = self.conn.execute(
            """
            SELECT id FROM context_bundle
            WHERE task_id = ?
            ORDER BY generated_at DESC
            """,
            (task_id,),
        )

        bundles = []
        for row in cursor.fetchall():
            bundle = self.get_bundle(row[0])
            if bundle:
                bundles.append(bundle)

        return bundles

    def _load_sources(self, bundle_id: str) -> List[BundleSource]:
        """Load sources for a bundle."""
        cursor = self.conn.execute(
            """
            SELECT id, context_bundle_id, typed_ref, source_kind, selected_raw, metadata_json, created_at
            FROM context_bundle_source
            WHERE context_bundle_id = ?
            ORDER BY created_at ASC
            """,
            (bundle_id,),
        )

        sources = []
        for row in cursor.fetchall():
            sources.append(
                BundleSource(
                    id=row[0],
                    context_bundle_id=row[1],
                    typed_ref=row[2],
                    source_kind=row[3],
                    selected_raw=bool(row[4]),
                    metadata_json=row[5],
                )
            )

        return sources


def create_bundle_tables(conn: sqlite3.Connection) -> None:
    """Create context bundle tables if they don't exist."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS context_bundle (
            id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
            purpose TEXT NOT NULL,
            rebuild_level TEXT NOT NULL,
            summary TEXT,
            state_snapshot_json TEXT NOT NULL,
            decision_digest_json TEXT,
            question_digest_json TEXT,
            diagnostics_json TEXT,
            raw_included INTEGER NOT NULL DEFAULT 0,
            generator_version TEXT NOT NULL,
            generated_at TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (task_id) REFERENCES task(id)
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS context_bundle_source (
            id TEXT PRIMARY KEY,
            context_bundle_id TEXT NOT NULL,
            typed_ref TEXT NOT NULL,
            source_kind TEXT NOT NULL,
            selected_raw INTEGER NOT NULL DEFAULT 0,
            metadata_json TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (context_bundle_id) REFERENCES context_bundle(id)
        )
        """
    )

    _ensure_column(conn, "context_bundle", "diagnostics_json", "TEXT")
    _ensure_column(
        conn,
        "context_bundle_source",
        "selected_raw",
        "INTEGER NOT NULL DEFAULT 0",
    )
    _ensure_column(conn, "context_bundle_source", "metadata_json", "TEXT")

    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_context_bundle_task
        ON context_bundle(task_id, generated_at DESC)
        """
    )

    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_context_bundle_source_bundle
        ON context_bundle_source(context_bundle_id)
        """
    )


def _ensure_column(
    conn: sqlite3.Connection,
    table_name: str,
    column_name: str,
    column_ddl: str,
) -> None:
    """Add a missing column to an existing table."""
    existing_columns = {
        row[1] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    }
    if column_name not in existing_columns:
        conn.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_ddl}"
        )

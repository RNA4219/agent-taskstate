"""
Context Bundle Service

Manages context bundle creation and audit trails.

Key features:
- Bundle generation with source refs tracking
- Audit information (purpose, rebuild_level, generator_version)
- Source refs stored in separate table for auditability
- gzip compression for large JSON fields
- LRU cache for latest bundle retrieval
- Differential bundle storage for incremental updates
"""

from __future__ import annotations

import gzip
import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .typed_ref import canonicalize_ref

# Compression threshold: compress if JSON exceeds this size (bytes)
COMPRESSION_THRESHOLD = 1024  # 1KB


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
    # Compression flags (stored separately in DB)
    _state_snapshot_compressed: bool = False
    _decision_digest_compressed: bool = False
    _question_digest_compressed: bool = False
    _diagnostics_compressed: bool = False

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
            "state_snapshot": decompress_json(
                self.state_snapshot_json, self._state_snapshot_compressed
            ),
            "decision_digest": decompress_json(
                self.decision_digest_json, self._decision_digest_compressed
            )
            if self.decision_digest_json
            else None,
            "question_digest": decompress_json(
                self.question_digest_json, self._question_digest_compressed
            )
            if self.question_digest_json
            else None,
            "diagnostics": decompress_json(self.diagnostics_json, self._diagnostics_compressed)
            if self.diagnostics_json
            else None,
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


def compress_json(data: Any, threshold: int = COMPRESSION_THRESHOLD) -> Tuple[str, bool]:
    """
    Compress JSON data if it exceeds threshold.

    Returns:
        (stored_data, is_compressed) tuple
    """
    json_str = json.dumps(data)
    if len(json_str) < threshold:
        return (json_str, False)

    compressed = gzip.compress(json_str.encode("utf-8"))
    # Store as base64-encoded string for SQLite TEXT column
    import base64

    return (base64.b64encode(compressed).decode("ascii"), True)


def decompress_json(stored_data: str, is_compressed: bool) -> Any:
    """
    Decompress JSON data if it was compressed.

    Args:
        stored_data: Stored string (either raw JSON or base64-encoded gzip)
        is_compressed: Whether the data was compressed

    Returns:
        Parsed JSON object
    """
    if not is_compressed:
        return json.loads(stored_data)

    import base64

    compressed = base64.b64decode(stored_data.encode("ascii"))
    json_str = gzip.decompress(compressed).decode("utf-8")
    return json.loads(json_str)


def compute_diff(
    prev_bundle: Optional[ContextBundle], new_snapshot: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Compute differential update between bundles.

    Returns only changed fields to reduce storage.
    """
    if prev_bundle is None:
        return new_snapshot

    prev_snapshot = decompress_json(
        prev_bundle.state_snapshot_json, prev_bundle._state_snapshot_compressed
    )

    diff = {}
    for key, new_val in new_snapshot.items():
        prev_val = prev_snapshot.get(key)
        if new_val != prev_val:
            diff[key] = new_val

    return diff if diff else new_snapshot


def decompress_bundle_json(bundle: ContextBundle) -> Dict[str, Any]:
    """Decompress all JSON fields in a bundle."""
    result = {}

    # state_snapshot_json is always present
    is_compressed = getattr(bundle, "_state_snapshot_compressed", False)
    result["state_snapshot"] = decompress_json(bundle.state_snapshot_json, is_compressed)

    # Optional JSON fields
    if bundle.decision_digest_json:
        is_compressed = getattr(bundle, "_decision_digest_compressed", False)
        result["decision_digest"] = decompress_json(bundle.decision_digest_json, is_compressed)

    if bundle.question_digest_json:
        is_compressed = getattr(bundle, "_question_digest_compressed", False)
        result["question_digest"] = decompress_json(bundle.question_digest_json, is_compressed)

    if bundle.diagnostics_json:
        is_compressed = getattr(bundle, "_diagnostics_compressed", False)
        result["diagnostics"] = decompress_json(bundle.diagnostics_json, is_compressed)

    return result


def now_utc() -> str:
    """Return current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def gen_id() -> str:
    """Generate a unique ID."""
    import uuid

    return uuid.uuid4().hex


class ContextBundleService:
    """Service for creating and managing context bundles."""

    _cache_max_size: int = 100

    def __init__(self, conn: sqlite3.Connection, generator_version: str = "1.0.0"):
        self.conn = conn
        self.generator_version = generator_version
        self._latest_cache: Dict[str, ContextBundle] = {}

    def clear_cache(self) -> None:
        """Clear the latest bundle cache."""
        self._latest_cache.clear()

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
        use_diff: bool = False,
    ) -> ContextBundle:
        """
        Create a new context bundle.

        Args:
            use_diff: If True, compute differential against previous bundle
        """
        if purpose not in PURPOSE_TYPES:
            raise ValueError(f"Invalid purpose: {purpose}")
        if rebuild_level not in REBUILD_LEVELS:
            raise ValueError(f"Invalid rebuild_level: {rebuild_level}")

        bundle_id = gen_id()
        now = now_utc()

        # 1.1.0 always stores a complete immutable snapshot; use_diff is compatibility-only.

        # Compress JSON fields
        state_data, state_compressed = compress_json(state_snapshot)
        decision_data, decision_compressed = (
            compress_json(decision_digest) if decision_digest else (None, False)
        )
        question_data, question_compressed = (
            compress_json(question_digest) if question_digest else (None, False)
        )
        diag_data, diag_compressed = compress_json(diagnostics) if diagnostics else (None, False)

        self.conn.execute(
            """
            INSERT INTO context_bundle
                (id, task_id, purpose, rebuild_level, summary, state_snapshot_json,
                 decision_digest_json, question_digest_json, diagnostics_json, raw_included,
                 generator_version, generated_at, created_at,
                 state_snapshot_compressed, decision_digest_compressed, question_digest_compressed, diagnostics_compressed)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                bundle_id,
                task_id,
                purpose,
                rebuild_level,
                summary,
                state_data,
                decision_data,
                question_data,
                diag_data,
                1 if raw_included else 0,
                self.generator_version,
                now,
                now,
                1 if state_compressed else 0,
                1 if decision_compressed else 0,
                1 if question_compressed else 0,
                1 if diag_compressed else 0,
            ),
        )

        bundle = ContextBundle(
            id=bundle_id,
            task_id=task_id,
            purpose=purpose,
            rebuild_level=rebuild_level,
            summary=summary,
            state_snapshot_json=state_data,
            decision_digest_json=decision_data,
            question_digest_json=question_data,
            diagnostics_json=diag_data,
            raw_included=raw_included,
            generator_version=self.generator_version,
            generated_at=now,
            created_at=now,
            _state_snapshot_compressed=state_compressed,
            _decision_digest_compressed=decision_compressed,
            _question_digest_compressed=question_compressed,
            _diagnostics_compressed=diag_compressed,
        )

        # Invalidate cache for this task
        if task_id in self._latest_cache:
            del self._latest_cache[task_id]

        return bundle

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
                   generator_version, generated_at, created_at,
                   state_snapshot_compressed, decision_digest_compressed, question_digest_compressed, diagnostics_compressed
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
            _state_snapshot_compressed=bool(row[13]) if len(row) > 13 else False,
            _decision_digest_compressed=bool(row[14]) if len(row) > 14 else False,
            _question_digest_compressed=bool(row[15]) if len(row) > 15 else False,
            _diagnostics_compressed=bool(row[16]) if len(row) > 16 else False,
        )
        bundle.sources = self._load_sources(bundle_id)
        return bundle

    def _get_latest_bundle_no_cache(self, task_id: str) -> Optional[ContextBundle]:
        """Get latest bundle without using cache."""
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

    def get_latest_bundle(self, task_id: str) -> Optional[ContextBundle]:
        """Get the latest context bundle for a task (cached)."""
        # Check cache first
        if task_id in self._latest_cache:
            return self._latest_cache[task_id]

        bundle = self._get_latest_bundle_no_cache(task_id)
        if bundle:
            # Manage cache size
            if len(self._latest_cache) >= self._cache_max_size:
                # Remove oldest entry (simple FIFO)
                oldest_key = next(iter(self._latest_cache))
                del self._latest_cache[oldest_key]
            self._latest_cache[task_id] = bundle

        return bundle

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

    # Compression flag columns for gzip-compressed JSON fields
    _ensure_column(
        conn, "context_bundle", "state_snapshot_compressed", "INTEGER NOT NULL DEFAULT 0"
    )
    _ensure_column(
        conn, "context_bundle", "decision_digest_compressed", "INTEGER NOT NULL DEFAULT 0"
    )
    _ensure_column(
        conn, "context_bundle", "question_digest_compressed", "INTEGER NOT NULL DEFAULT 0"
    )
    _ensure_column(conn, "context_bundle", "diagnostics_compressed", "INTEGER NOT NULL DEFAULT 0")

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
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_ddl}")


class ContextRebuildService:
    """Build complete, immutable plural snapshots with resolver diagnostics."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        resolver: Optional[Any] = None,
        generator_version: str = "1.1.0",
    ):
        self.conn = conn
        self.generator_version = generator_version
        self.resolver = resolver
        self._latest_cache: Dict[str, ContextBundle] = {}

    def clear_cache(self) -> None:
        self._latest_cache.clear()

    @staticmethod
    def _json(value: Optional[str], default: Any) -> Any:
        if not value:
            return default
        try:
            return json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return default

    def build(
        self,
        task_id: str,
        purpose: str = "continue_work",
        rebuild_level: str = "L2",
        include_raw: bool = False,
        reason: Optional[str] = None,
    ) -> ContextBundle:
        if purpose not in PURPOSE_TYPES:
            raise ValueError(f"Invalid purpose: {purpose}")
        if rebuild_level not in REBUILD_LEVELS:
            raise ValueError(f"Invalid rebuild_level: {rebuild_level}")

        task_row = self.conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if task_row is None:
            raise ValueError(f"Task not found: {task_id}")
        state_row = self.conn.execute(
            "SELECT * FROM task_states WHERE task_id = ?", (task_id,)
        ).fetchone()
        state: Dict[str, Any] = {
            "task_id": task_id,
            "revision": 0,
            "current_step": None,
            "constraints": [],
            "done_when": [],
            "current_summary": None,
            "artifact_refs": [],
            "evidence_refs": [],
            "confidence": None,
            "context_policy": {},
        }
        if state_row is not None:
            state = {
                "task_id": state_row["task_id"],
                "revision": state_row["revision"],
                "current_step": state_row["current_step"],
                "constraints": self._json(state_row["constraints_json"], []),
                "done_when": self._json(state_row["done_when_json"], []),
                "current_summary": state_row["current_summary"],
                "artifact_refs": self._json(state_row["artifact_refs_json"], []),
                "evidence_refs": self._json(state_row["evidence_refs_json"], []),
                "confidence": state_row["confidence"],
                "context_policy": self._json(state_row["context_policy_json"], {}),
            }
        decisions = [
            dict(row)
            for row in self.conn.execute(
                "SELECT * FROM decisions WHERE task_id = ? AND status IN ('accepted', 'proposed') ORDER BY created_at ASC",
                (task_id,),
            ).fetchall()
        ]
        for item in decisions:
            item["evidence_refs"] = self._json(item.pop("evidence_refs_json", None), [])
            item["ref"] = f"agent-taskstate:decision:local:{item['id']}"
        questions = [
            dict(row)
            for row in self.conn.execute(
                "SELECT * FROM open_questions WHERE task_id = ? AND status = 'open' ORDER BY created_at ASC",
                (task_id,),
            ).fetchall()
        ]
        for item in questions:
            item["evidence_refs"] = self._json(item.pop("evidence_refs_json", None), [])
            item["ref"] = f"agent-taskstate:question:local:{item['id']}"
        runs = [
            dict(row)
            for row in self.conn.execute(
                "SELECT * FROM runs WHERE task_id = ? ORDER BY created_at ASC", (task_id,)
            ).fetchall()
        ]
        for item in runs:
            item["ref"] = f"agent-taskstate:run:local:{item['id']}"

        task = dict(task_row)
        refs: List[tuple[str, str]] = [("task", f"agent-taskstate:task:local:{task_id}")]
        refs.extend(("decision", item["ref"]) for item in decisions)
        refs.extend(("open_question", item["ref"]) for item in questions)
        refs.extend(("run", item["ref"]) for item in runs)
        for kind in ("artifact", "evidence"):
            values: List[Any] = state.get(f"{kind}_refs", [])
            for raw_ref in values:
                try:
                    refs.append((kind, canonicalize_ref(str(raw_ref))))
                except ValueError:
                    continue

        diagnostics: Dict[str, Any] = {
            "missing_refs": [],
            "unsupported_refs": [],
            "resolver_warnings": [],
            "partial_bundle": False,
        }
        resolved_summaries: List[Dict[str, Any]] = []
        selected_raw: Dict[str, Any] = {}
        selected_refs: set[str] = set()
        resolver: Any = self.resolver
        if resolver is None:
            from .resolver import (
                AgentTaskstateLocalResolver,
                ContextRebuildResolver,
                MemxResolver,
                TrackerResolver,
            )

            resolver = ContextRebuildResolver()
            resolver.register_resolver(AgentTaskstateLocalResolver(self.conn))
            resolver.register_resolver(MemxResolver())
            resolver.register_resolver(TrackerResolver())
        ref_values = [ref for _, ref in refs]
        try:
            report = resolver.resolve_many(ref_values)
            diagnostics = resolver.get_diagnostics(report).to_dict()
            resolved_summaries = [
                {"ref": item.ref, "summary": item.summary, "metadata": item.metadata or {}}
                for item in report.resolved
            ]
            if include_raw:
                for item in report.resolved:
                    if not item.raw_available:
                        continue
                    raw = resolver.load_selected_raw(item.ref)
                    if raw is not None:
                        selected_raw[item.ref] = {"content": raw.content, "metadata": raw.metadata}
                        selected_refs.add(item.ref)
        except Exception as exc:
            diagnostics["resolver_warnings"].append(f"{type(exc).__name__}: {exc}")
            diagnostics["partial_bundle"] = True

        now = now_utc()
        bundle_id = gen_id()
        build_reason = reason or purpose
        decision_refs = [item["ref"] for item in decisions]
        question_refs = [item["ref"] for item in questions]
        artifact_refs = [ref for kind, ref in refs if kind == "artifact"]
        evidence_refs = [ref for kind, ref in refs if kind == "evidence"]
        snapshot = {
            "task": task,
            "task_state": state,
            "decisions": decisions,
            "open_questions": questions,
            "runs": runs,
            "resolved_summaries": resolved_summaries,
            "selected_raw": selected_raw,
            "purpose": purpose,
            "rebuild_level": rebuild_level,
        }
        decision_digest = {"refs": decision_refs, "items": decisions}
        question_digest = {"refs": question_refs, "items": questions}
        summary = str(state.get("current_summary") or task.get("title") or "context rebuild")

        self.conn.execute(
            """
            INSERT INTO context_bundles (
              id, task_id, build_reason, state_snapshot_json, included_decision_refs_json,
              included_open_question_refs_json, included_artifact_refs_json, included_evidence_refs_json,
              expected_output_schema_json, created_at, metadata_json, purpose, rebuild_level,
              summary, decision_digest_json, question_digest_json, diagnostics_json, raw_included,
              generator_version, generated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                bundle_id,
                task_id,
                build_reason,
                json.dumps(snapshot, ensure_ascii=False),
                json.dumps(decision_refs),
                json.dumps(question_refs),
                json.dumps(artifact_refs),
                json.dumps(evidence_refs),
                json.dumps(
                    {
                        "summary": "string",
                        "proposed_actions": ["string"],
                        "decision_candidates": ["string"],
                        "question_candidates": ["string"],
                        "evidence_needed": ["string"],
                    }
                ),
                now,
                json.dumps({"full_snapshot": True}, ensure_ascii=False),
                purpose,
                rebuild_level,
                summary,
                json.dumps(decision_digest, ensure_ascii=False),
                json.dumps(question_digest, ensure_ascii=False),
                json.dumps(diagnostics, ensure_ascii=False),
                1 if include_raw and selected_raw else 0,
                self.generator_version,
                now,
            ),
        )
        sources: List[BundleSource] = []
        for kind, ref in refs:
            source_id = gen_id()
            selected = ref in selected_refs
            self.conn.execute(
                """
                INSERT INTO context_bundle_sources
                  (id, context_bundle_id, typed_ref, source_kind, selected_raw, metadata_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source_id,
                    bundle_id,
                    ref,
                    kind,
                    1 if selected else 0,
                    json.dumps({"resolver": "summary-first"}, ensure_ascii=False),
                    now,
                ),
            )
            sources.append(
                BundleSource(
                    source_id,
                    bundle_id,
                    ref,
                    kind,
                    selected,
                    json.dumps({"resolver": "summary-first"}),
                )
            )
        bundle = ContextBundle(
            id=bundle_id,
            task_id=task_id,
            purpose=purpose,
            rebuild_level=rebuild_level,
            summary=summary,
            state_snapshot_json=json.dumps(snapshot, ensure_ascii=False),
            decision_digest_json=json.dumps(decision_digest, ensure_ascii=False),
            question_digest_json=json.dumps(question_digest, ensure_ascii=False),
            diagnostics_json=json.dumps(diagnostics, ensure_ascii=False),
            raw_included=bool(include_raw and selected_raw),
            generator_version=self.generator_version,
            generated_at=now,
            created_at=now,
            sources=sources,
        )
        self._latest_cache[task_id] = bundle
        return bundle

    def get_latest_bundle(self, task_id: str) -> Optional[ContextBundle]:
        if task_id in self._latest_cache:
            return self._latest_cache[task_id]
        row = self.conn.execute(
            "SELECT * FROM context_bundles WHERE task_id = ? ORDER BY generated_at DESC, created_at DESC LIMIT 1",
            (task_id,),
        ).fetchone()
        if row is None:
            return None
        data = dict(row)
        bundle = ContextBundle(
            id=data["id"],
            task_id=data["task_id"],
            purpose=data.get("purpose") or "continue_work",
            rebuild_level=data.get("rebuild_level") or "L2",
            summary=(str(data.get("summary")) if data.get("summary") is not None else None),
            state_snapshot_json=data["state_snapshot_json"],
            decision_digest_json=data.get("decision_digest_json"),
            question_digest_json=data.get("question_digest_json"),
            diagnostics_json=data.get("diagnostics_json"),
            raw_included=bool(data.get("raw_included", 0)),
            generator_version=data.get("generator_version") or "legacy/1.0.1",
            generated_at=data.get("generated_at") or data["created_at"],
            created_at=data["created_at"],
        )
        sources = self.conn.execute(
            "SELECT id, context_bundle_id, typed_ref, source_kind, selected_raw, metadata_json FROM context_bundle_sources WHERE context_bundle_id = ? ORDER BY created_at ASC",
            (bundle.id,),
        ).fetchall()
        bundle.sources = [
            BundleSource(
                id=source["id"],
                context_bundle_id=source["context_bundle_id"],
                typed_ref=source["typed_ref"],
                source_kind=source["source_kind"],
                selected_raw=bool(source["selected_raw"]),
                metadata_json=source["metadata_json"],
            )
            for source in sources
        ]
        self._latest_cache[task_id] = bundle
        return bundle

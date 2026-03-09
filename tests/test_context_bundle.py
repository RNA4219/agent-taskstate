"""
Tests for context_bundle module.

Covers:
- Bundle creation with audit info
- Source refs management
- Bundle retrieval and listing
"""

import json
import sqlite3

import pytest

from src.context_bundle import (
    ContextBundleService,
    create_bundle_tables,
    PURPOSE_TYPES,
    REBUILD_LEVELS,
    SOURCE_KINDS,
)


@pytest.fixture
def conn():
    """Create an in-memory database with required tables."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    conn.execute(
        """
        CREATE TABLE task (
            id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "INSERT INTO task (id, status, updated_at) VALUES (?, ?, ?)",
        ("task_001", "in_progress", "2024-01-01T00:00:00.000000Z"),
    )

    create_bundle_tables(conn)

    yield conn
    conn.close()


@pytest.fixture
def service(conn):
    """Create a ContextBundleService instance."""
    return ContextBundleService(conn, generator_version="1.0.0")


class TestConstants:
    """Test module constants."""

    def test_rebuild_levels(self):
        assert "L1" in REBUILD_LEVELS
        assert "L2" in REBUILD_LEVELS
        assert "L3" in REBUILD_LEVELS

    def test_purpose_types(self):
        assert "continue_work" in PURPOSE_TYPES
        assert "review_prepare" in PURPOSE_TYPES
        assert "decision_support" in PURPOSE_TYPES

    def test_source_kinds(self):
        assert "task" in SOURCE_KINDS
        assert "decision" in SOURCE_KINDS
        assert "evidence" in SOURCE_KINDS


class TestContextBundleService:
    """Test ContextBundleService."""

    def test_create_bundle(self, service):
        bundle = service.create_bundle(
            task_id="task_001",
            purpose="continue_work",
            rebuild_level="L1",
            state_snapshot={"status": "in_progress", "step": 1},
        )

        assert bundle.task_id == "task_001"
        assert bundle.purpose == "continue_work"
        assert bundle.rebuild_level == "L1"
        assert bundle.raw_included is False
        assert bundle.generator_version == "1.0.0"

    def test_create_bundle_with_digests(self, service):
        bundle = service.create_bundle(
            task_id="task_001",
            purpose="review_prepare",
            rebuild_level="L2",
            state_snapshot={"status": "review"},
            decision_digest={"accepted": 3, "proposed": 1},
            question_digest={"open": 2, "answered": 5},
            diagnostics={"missing_refs": [], "partial_bundle": False},
            summary="Ready for review",
            raw_included=True,
        )

        assert bundle.summary == "Ready for review"
        assert bundle.raw_included is True

        decision_digest = json.loads(bundle.decision_digest_json)
        assert decision_digest["accepted"] == 3

        question_digest = json.loads(bundle.question_digest_json)
        assert question_digest["open"] == 2

        diagnostics = json.loads(bundle.diagnostics_json)
        assert diagnostics["partial_bundle"] is False

    def test_invalid_purpose_raises(self, service):
        with pytest.raises(ValueError, match="Invalid purpose"):
            service.create_bundle(
                task_id="task_001",
                purpose="invalid_purpose",
                rebuild_level="L1",
                state_snapshot={},
            )

    def test_invalid_rebuild_level_raises(self, service):
        with pytest.raises(ValueError, match="Invalid rebuild_level"):
            service.create_bundle(
                task_id="task_001",
                purpose="continue_work",
                rebuild_level="L4",
                state_snapshot={},
            )

    def test_add_source(self, service):
        bundle = service.create_bundle(
            task_id="task_001",
            purpose="continue_work",
            rebuild_level="L1",
            state_snapshot={},
        )

        source = service.add_source(
            bundle_id=bundle.id,
            typed_ref="agent-taskstate:decision:local:dec_001",
            source_kind="decision",
        )

        assert source.context_bundle_id == bundle.id
        assert source.typed_ref == "agent-taskstate:decision:local:dec_001"
        assert source.source_kind == "decision"

    def test_add_source_canonicalizes_ref(self, service):
        bundle = service.create_bundle(
            task_id="task_001",
            purpose="continue_work",
            rebuild_level="L1",
            state_snapshot={},
        )

        source = service.add_source(
            bundle_id=bundle.id,
            typed_ref="agent-taskstate:decision:dec_001",
            source_kind="decision",
        )

        assert source.typed_ref == "agent-taskstate:decision:local:dec_001"

    def test_invalid_source_kind_raises(self, service):
        bundle = service.create_bundle(
            task_id="task_001",
            purpose="continue_work",
            rebuild_level="L1",
            state_snapshot={},
        )

        with pytest.raises(ValueError, match="Invalid source_kind"):
            service.add_source(
                bundle_id=bundle.id,
                typed_ref="agent-taskstate:task:local:task_001",
                source_kind="invalid_kind",
            )

    def test_add_source_persists_selected_raw_and_metadata(self, service):
        bundle = service.create_bundle(
            task_id="task_001",
            purpose="continue_work",
            rebuild_level="L1",
            state_snapshot={},
        )

        service.add_source(
            bundle_id=bundle.id,
            typed_ref="memx:evidence:local:ev_001",
            source_kind="evidence",
            selected_raw=True,
            metadata={"selector": {"lines": [1, 2]}},
        )

        retrieved = service.get_bundle(bundle.id)
        assert retrieved is not None
        assert len(retrieved.sources) == 1
        assert retrieved.sources[0].selected_raw is True
        assert json.loads(retrieved.sources[0].metadata_json) == {
            "selector": {"lines": [1, 2]}
        }

    def test_get_bundle(self, service):
        created = service.create_bundle(
            task_id="task_001",
            purpose="continue_work",
            rebuild_level="L1",
            state_snapshot={"step": 1},
        )

        service.add_source(created.id, "agent-taskstate:decision:local:dec_001", "decision")
        service.add_source(created.id, "agent-taskstate:artifact:local:art_001", "artifact")

        retrieved = service.get_bundle(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert len(retrieved.sources) == 2

    def test_get_bundle_not_found(self, service):
        result = service.get_bundle("nonexistent")
        assert result is None

    def test_get_latest_bundle(self, service):
        service.create_bundle(
            task_id="task_001",
            purpose="continue_work",
            rebuild_level="L1",
            state_snapshot={"step": 1},
        )

        service.create_bundle(
            task_id="task_001",
            purpose="review_prepare",
            rebuild_level="L2",
            state_snapshot={"step": 2},
        )

        bundles = service.list_bundles("task_001")
        assert len(bundles) == 2

        purposes = [b.purpose for b in bundles]
        assert "continue_work" in purposes
        assert "review_prepare" in purposes

    def test_get_latest_bundle_no_bundles(self, service):
        service.conn.execute(
            "INSERT INTO task (id, status, updated_at) VALUES (?, ?, ?)",
            ("task_002", "proposed", "2024-01-01T00:00:00.000000Z"),
        )

        result = service.get_latest_bundle("task_002")
        assert result is None

    def test_list_bundles(self, service):
        service.create_bundle(
            task_id="task_001",
            purpose="continue_work",
            rebuild_level="L1",
            state_snapshot={},
        )

        service.create_bundle(
            task_id="task_001",
            purpose="review_prepare",
            rebuild_level="L2",
            state_snapshot={},
        )

        bundles = service.list_bundles("task_001")

        assert len(bundles) == 2
        purposes = [b.purpose for b in bundles]
        assert "continue_work" in purposes
        assert "review_prepare" in purposes


class TestContextBundle:
    """Test ContextBundle dataclass."""

    def test_to_dict(self, service):
        bundle = service.create_bundle(
            task_id="task_001",
            purpose="continue_work",
            rebuild_level="L1",
            state_snapshot={"status": "in_progress"},
            diagnostics={"missing_refs": ["memx:evidence:local:ev_missing"]},
            summary="Test bundle",
        )

        service.add_source(
            bundle.id,
            "agent-taskstate:decision:local:dec_001",
            "decision",
            metadata={"kind": "decision"},
        )
        service.add_source(bundle.id, "agent-taskstate:artifact:local:art_001", "artifact")

        bundle = service.get_bundle(bundle.id)
        result = bundle.to_dict()

        assert result["id"] == bundle.id
        assert result["task_id"] == "task_001"
        assert result["purpose"] == "continue_work"
        assert result["summary"] == "Test bundle"
        assert result["state_snapshot"]["status"] == "in_progress"
        assert result["diagnostics"]["missing_refs"] == ["memx:evidence:local:ev_missing"]
        assert result["raw_included"] is False
        assert len(result["source_refs"]) == 2
        assert result["source_count"] == 2
        assert result["sources"][0]["metadata"] == {"kind": "decision"}

    def test_get_source_refs(self, service):
        bundle = service.create_bundle(
            task_id="task_001",
            purpose="continue_work",
            rebuild_level="L1",
            state_snapshot={},
        )

        service.add_source(bundle.id, "agent-taskstate:decision:local:dec_001", "decision")
        service.add_source(bundle.id, "agent-taskstate:evidence:local:ev_001", "evidence")

        bundle = service.get_bundle(bundle.id)
        refs = bundle.get_source_refs()

        assert len(refs) == 2
        assert "agent-taskstate:decision:local:dec_001" in refs
        assert "agent-taskstate:evidence:local:ev_001" in refs


class TestBundleAudit:
    """Test bundle audit features (P2 requirements)."""

    def test_bundle_has_purpose(self, service):
        bundle = service.create_bundle(
            task_id="task_001",
            purpose="decision_support",
            rebuild_level="L2",
            state_snapshot={},
        )

        assert bundle.purpose == "decision_support"

    def test_bundle_has_rebuild_level(self, service):
        bundle = service.create_bundle(
            task_id="task_001",
            purpose="continue_work",
            rebuild_level="L3",
            state_snapshot={},
        )

        assert bundle.rebuild_level == "L3"

    def test_bundle_has_raw_included_flag(self, service):
        bundle_raw_false = service.create_bundle(
            task_id="task_001",
            purpose="continue_work",
            rebuild_level="L1",
            state_snapshot={},
            raw_included=False,
        )

        bundle_raw_true = service.create_bundle(
            task_id="task_001",
            purpose="review_prepare",
            rebuild_level="L2",
            state_snapshot={},
            raw_included=True,
        )

        assert bundle_raw_false.raw_included is False
        assert bundle_raw_true.raw_included is True

    def test_bundle_has_generator_version(self, service):
        bundle = service.create_bundle(
            task_id="task_001",
            purpose="continue_work",
            rebuild_level="L1",
            state_snapshot={},
        )

        assert bundle.generator_version == "1.0.0"

    def test_bundle_source_refs_listed(self, service):
        bundle = service.create_bundle(
            task_id="task_001",
            purpose="continue_work",
            rebuild_level="L2",
            state_snapshot={},
        )

        service.add_source(bundle.id, "agent-taskstate:task:local:task_001", "task")
        service.add_source(bundle.id, "agent-taskstate:decision:local:dec_001", "decision")
        service.add_source(bundle.id, "memx:evidence:local:ev_001", "evidence")

        retrieved = service.get_bundle(bundle.id)
        refs = retrieved.get_source_refs()

        assert len(refs) == 3

    def test_bundle_generated_at_timestamp(self, service):
        bundle = service.create_bundle(
            task_id="task_001",
            purpose="continue_work",
            rebuild_level="L1",
            state_snapshot={},
        )

        assert bundle.generated_at is not None
        assert "T" in bundle.generated_at

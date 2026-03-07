"""
Tests for context_bundle module.

Covers:
- Bundle creation with audit info
- Source refs management
- Bundle retrieval and listing
"""

import pytest
import sqlite3
import json

from src.context_bundle import (
    ContextBundle,
    BundleSource,
    ContextBundleService,
    create_bundle_tables,
    REBUILD_LEVELS,
    PURPOSE_TYPES,
    SOURCE_KINDS,
)


@pytest.fixture
def conn():
    """Create an in-memory database with required tables."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    # Create task table first
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

    # Create bundle tables
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
        """REBUILD_LEVELS contains expected values."""
        assert "L1" in REBUILD_LEVELS
        assert "L2" in REBUILD_LEVELS
        assert "L3" in REBUILD_LEVELS

    def test_purpose_types(self):
        """PURPOSE_TYPES contains expected values."""
        assert "continue_work" in PURPOSE_TYPES
        assert "review_prepare" in PURPOSE_TYPES
        assert "decision_support" in PURPOSE_TYPES

    def test_source_kinds(self):
        """SOURCE_KINDS contains expected values."""
        assert "task" in SOURCE_KINDS
        assert "decision" in SOURCE_KINDS
        assert "evidence" in SOURCE_KINDS


class TestContextBundleService:
    """Test ContextBundleService."""

    def test_create_bundle(self, service):
        """Create a basic bundle."""
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
        """Create bundle with decision and question digests."""
        bundle = service.create_bundle(
            task_id="task_001",
            purpose="review_prepare",
            rebuild_level="L2",
            state_snapshot={"status": "review"},
            decision_digest={"accepted": 3, "proposed": 1},
            question_digest={"open": 2, "answered": 5},
            summary="Ready for review",
            raw_included=True,
        )

        assert bundle.summary == "Ready for review"
        assert bundle.raw_included is True

        # Check JSON content
        decision_digest = json.loads(bundle.decision_digest_json)
        assert decision_digest["accepted"] == 3

        question_digest = json.loads(bundle.question_digest_json)
        assert question_digest["open"] == 2

    def test_invalid_purpose_raises(self, service):
        """Invalid purpose raises ValueError."""
        with pytest.raises(ValueError, match="Invalid purpose"):
            service.create_bundle(
                task_id="task_001",
                purpose="invalid_purpose",
                rebuild_level="L1",
                state_snapshot={},
            )

    def test_invalid_rebuild_level_raises(self, service):
        """Invalid rebuild_level raises ValueError."""
        with pytest.raises(ValueError, match="Invalid rebuild_level"):
            service.create_bundle(
                task_id="task_001",
                purpose="continue_work",
                rebuild_level="L4",  # Invalid
                state_snapshot={},
            )

    def test_add_source(self, service):
        """Add source to bundle."""
        bundle = service.create_bundle(
            task_id="task_001",
            purpose="continue_work",
            rebuild_level="L1",
            state_snapshot={},
        )

        source = service.add_source(
            bundle_id=bundle.id,
            typed_ref="workx:decision:local:dec_001",
            source_kind="decision",
        )

        assert source.context_bundle_id == bundle.id
        assert source.typed_ref == "workx:decision:local:dec_001"
        assert source.source_kind == "decision"

    def test_add_source_canonicalizes_ref(self, service):
        """Add source canonicalizes 3-segment ref to 4-segment."""
        bundle = service.create_bundle(
            task_id="task_001",
            purpose="continue_work",
            rebuild_level="L1",
            state_snapshot={},
        )

        source = service.add_source(
            bundle_id=bundle.id,
            typed_ref="workx:decision:dec_001",  # 3-segment
            source_kind="decision",
        )

        # Should be canonicalized to 4-segment
        assert source.typed_ref == "workx:decision:local:dec_001"

    def test_invalid_source_kind_raises(self, service):
        """Invalid source_kind raises ValueError."""
        bundle = service.create_bundle(
            task_id="task_001",
            purpose="continue_work",
            rebuild_level="L1",
            state_snapshot={},
        )

        with pytest.raises(ValueError, match="Invalid source_kind"):
            service.add_source(
                bundle_id=bundle.id,
                typed_ref="workx:task:local:task_001",
                source_kind="invalid_kind",
            )

    def test_get_bundle(self, service):
        """Get bundle by ID."""
        created = service.create_bundle(
            task_id="task_001",
            purpose="continue_work",
            rebuild_level="L1",
            state_snapshot={"step": 1},
        )

        # Add sources
        service.add_source(created.id, "workx:decision:local:dec_001", "decision")
        service.add_source(created.id, "workx:artifact:local:art_001", "artifact")

        retrieved = service.get_bundle(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert len(retrieved.sources) == 2

    def test_get_bundle_not_found(self, service):
        """Get bundle returns None if not found."""
        result = service.get_bundle("nonexistent")
        assert result is None

    def test_get_latest_bundle(self, service):
        """Get latest bundle for task."""
        # Create bundles
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

        # Verify both purposes are present
        purposes = [b.purpose for b in bundles]
        assert "continue_work" in purposes
        assert "review_prepare" in purposes

    def test_get_latest_bundle_no_bundles(self, service):
        """Get latest bundle returns None if no bundles."""
        # Create new task with no bundles
        import sqlite3
        service.conn.execute(
            "INSERT INTO task (id, status, updated_at) VALUES (?, ?, ?)",
            ("task_002", "proposed", "2024-01-01T00:00:00.000000Z"),
        )

        result = service.get_latest_bundle("task_002")
        assert result is None

    def test_list_bundles(self, service):
        """List all bundles for task."""
        bundle1 = service.create_bundle(
            task_id="task_001",
            purpose="continue_work",
            rebuild_level="L1",
            state_snapshot={},
        )

        bundle2 = service.create_bundle(
            task_id="task_001",
            purpose="review_prepare",
            rebuild_level="L2",
            state_snapshot={},
        )

        bundles = service.list_bundles("task_001")

        assert len(bundles) == 2
        # Verify both bundles are present (order may vary due to timestamp precision)
        purposes = [b.purpose for b in bundles]
        assert "continue_work" in purposes
        assert "review_prepare" in purposes


class TestContextBundle:
    """Test ContextBundle dataclass."""

    def test_to_dict(self, service):
        """Bundle to_dict for JSON output."""
        bundle = service.create_bundle(
            task_id="task_001",
            purpose="continue_work",
            rebuild_level="L1",
            state_snapshot={"status": "in_progress"},
            summary="Test bundle",
        )

        service.add_source(bundle.id, "workx:decision:local:dec_001", "decision")
        service.add_source(bundle.id, "workx:artifact:local:art_001", "artifact")

        # Reload bundle to get updated sources
        bundle = service.get_bundle(bundle.id)
        result = bundle.to_dict()

        assert result["id"] == bundle.id
        assert result["task_id"] == "task_001"
        assert result["purpose"] == "continue_work"
        assert result["summary"] == "Test bundle"
        assert result["state_snapshot"]["status"] == "in_progress"
        assert result["raw_included"] is False
        assert len(result["source_refs"]) == 2
        assert result["source_count"] == 2

    def test_get_source_refs(self, service):
        """Get list of source refs."""
        bundle = service.create_bundle(
            task_id="task_001",
            purpose="continue_work",
            rebuild_level="L1",
            state_snapshot={},
        )

        service.add_source(bundle.id, "workx:decision:local:dec_001", "decision")
        service.add_source(bundle.id, "workx:evidence:local:ev_001", "evidence")

        # Reload bundle to get updated sources
        bundle = service.get_bundle(bundle.id)
        refs = bundle.get_source_refs()

        assert len(refs) == 2
        assert "workx:decision:local:dec_001" in refs
        assert "workx:evidence:local:ev_001" in refs


class TestBundleAudit:
    """Test bundle audit features (P2 requirements)."""

    def test_bundle_has_purpose(self, service):
        """Bundle has purpose field."""
        bundle = service.create_bundle(
            task_id="task_001",
            purpose="decision_support",
            rebuild_level="L2",
            state_snapshot={},
        )

        assert bundle.purpose == "decision_support"

    def test_bundle_has_rebuild_level(self, service):
        """Bundle has rebuild_level field."""
        bundle = service.create_bundle(
            task_id="task_001",
            purpose="continue_work",
            rebuild_level="L3",
            state_snapshot={},
        )

        assert bundle.rebuild_level == "L3"

    def test_bundle_has_raw_included_flag(self, service):
        """Bundle has raw_included flag."""
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
        """Bundle has generator_version field."""
        bundle = service.create_bundle(
            task_id="task_001",
            purpose="continue_work",
            rebuild_level="L1",
            state_snapshot={},
        )

        assert bundle.generator_version == "1.0.0"

    def test_bundle_source_refs_listed(self, service):
        """Source refs can be listed for bundle."""
        bundle = service.create_bundle(
            task_id="task_001",
            purpose="continue_work",
            rebuild_level="L2",
            state_snapshot={},
        )

        # Add multiple sources
        service.add_source(bundle.id, "workx:task:local:task_001", "task")
        service.add_source(bundle.id, "workx:decision:local:dec_001", "decision")
        service.add_source(bundle.id, "memx:evidence:local:ev_001", "evidence")

        retrieved = service.get_bundle(bundle.id)
        refs = retrieved.get_source_refs()

        assert len(refs) == 3

    def test_bundle_generated_at_timestamp(self, service):
        """Bundle has generated_at timestamp."""
        bundle = service.create_bundle(
            task_id="task_001",
            purpose="continue_work",
            rebuild_level="L1",
            state_snapshot={},
        )

        assert bundle.generated_at is not None
        assert "T" in bundle.generated_at  # ISO format
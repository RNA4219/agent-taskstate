"""Tests for ContextBundle compression and caching."""

import json
import pytest
import sqlite3
import tempfile

from src.context_bundle import (
    ContextBundle,
    ContextBundleService,
    BundleSource,
    compress_json,
    decompress_json,
    compute_diff,
    decompress_bundle_json,
    create_bundle_tables,
    COMPRESSION_THRESHOLD,
    REBUILD_LEVELS,
    PURPOSE_TYPES,
    SOURCE_KINDS,
)


@pytest.fixture
def conn():
    """Create in-memory database with bundle tables."""
    conn = sqlite3.connect(":memory:")
    # Create task table first (foreign key reference)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS task (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'proposed',
            goal TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    # Insert a test task
    conn.execute(
        "INSERT INTO task (id, title, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        ("task-001", "Test Task", "proposed", "2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z"),
    )
    create_bundle_tables(conn)
    yield conn
    conn.close()


@pytest.fixture
def service(conn):
    """Create ContextBundleService instance."""
    return ContextBundleService(conn, generator_version="test-1.0")


class TestCompression:
    """Test JSON compression utilities."""

    def test_compress_small_data(self):
        """Small data is not compressed."""
        small_data = {"key": "value"}
        stored, is_compressed = compress_json(small_data)
        assert is_compressed is False
        assert stored == json.dumps(small_data)

    def test_compress_large_data(self):
        """Large data is compressed."""
        large_data = {"data": "x" * COMPRESSION_THRESHOLD * 2}
        stored, is_compressed = compress_json(large_data)
        assert is_compressed is True
        assert len(stored) < len(json.dumps(large_data))

    def test_decompress_uncompressed(self):
        """Decompress handles uncompressed data."""
        data = {"key": "value"}
        stored, _ = compress_json(data)
        result = decompress_json(stored, False)
        assert result == data

    def test_decompress_compressed(self):
        """Decompress handles compressed data."""
        large_data = {"data": "x" * COMPRESSION_THRESHOLD * 2}
        stored, _ = compress_json(large_data)
        result = decompress_json(stored, True)
        assert result == large_data

    def test_compress_threshold_override(self):
        """Can override compression threshold."""
        data = {"small": "value"}
        stored, is_compressed = compress_json(data, threshold=10)
        # len(json.dumps(data)) ~ 20 bytes, so should compress with threshold=10
        assert is_compressed is True


class TestDifferential:
    """Test differential bundle computation."""

    def test_compute_diff_no_previous(self):
        """No previous bundle returns full snapshot."""
        snapshot = {"task_id": "001", "status": "in_progress"}
        result = compute_diff(None, snapshot)
        assert result == snapshot

    def test_compute_diff_no_changes(self):
        """No changes returns full snapshot (fallback)."""
        prev_bundle = ContextBundle(
            id="prev-001",
            task_id="task-001",
            purpose="continue_work",
            rebuild_level="L1",
            summary=None,
            state_snapshot_json=json.dumps({"task_id": "001", "status": "in_progress"}),
            decision_digest_json=None,
            question_digest_json=None,
            diagnostics_json=None,
            raw_included=False,
            generator_version="test",
            generated_at="2024-01-01T00:00:00Z",
            created_at="2024-01-01T00:00:00Z",
        )
        new_snapshot = {"task_id": "001", "status": "in_progress"}
        result = compute_diff(prev_bundle, new_snapshot)
        # Should return new snapshot when no diff (fallback)
        assert result == new_snapshot

    def test_compute_diff_with_changes(self):
        """Changed fields are included in diff."""
        prev_bundle = ContextBundle(
            id="prev-001",
            task_id="task-001",
            purpose="continue_work",
            rebuild_level="L1",
            summary=None,
            state_snapshot_json=json.dumps({"task_id": "001", "status": "in_progress", "goal": "old"}),
            decision_digest_json=None,
            question_digest_json=None,
            diagnostics_json=None,
            raw_included=False,
            generator_version="test",
            generated_at="2024-01-01T00:00:00Z",
            created_at="2024-01-01T00:00:00Z",
        )
        new_snapshot = {"task_id": "001", "status": "review", "goal": "old"}
        result = compute_diff(prev_bundle, new_snapshot)
        # Only status changed
        assert result == {"status": "review"}


class TestBundleCompression:
    """Test bundle creation with compression."""

    def test_create_bundle_small_snapshot(self, service):
        """Small snapshot is not compressed."""
        small_snapshot = {"task_id": "001", "status": "in_progress"}
        bundle = service.create_bundle(
            task_id="task-001",
            purpose="continue_work",
            rebuild_level="L1",
            state_snapshot=small_snapshot,
        )
        assert bundle._state_snapshot_compressed is False
        assert json.loads(bundle.state_snapshot_json) == small_snapshot

    def test_create_bundle_large_snapshot(self, service):
        """Large snapshot is compressed."""
        large_snapshot = {"data": "x" * COMPRESSION_THRESHOLD * 2, "status": "in_progress"}
        bundle = service.create_bundle(
            task_id="task-001",
            purpose="continue_work",
            rebuild_level="L1",
            state_snapshot=large_snapshot,
        )
        assert bundle._state_snapshot_compressed is True

    def test_create_bundle_with_compressed_digests(self, service):
        """Digests are also compressed if large."""
        large_digest = {"entries": ["x" * COMPRESSION_THRESHOLD * 2]}
        bundle = service.create_bundle(
            task_id="task-001",
            purpose="continue_work",
            rebuild_level="L1",
            state_snapshot={"status": "in_progress"},
            decision_digest=large_digest,
            question_digest=large_digest,
            diagnostics=large_digest,
        )
        assert bundle._decision_digest_compressed is True
        assert bundle._question_digest_compressed is True
        assert bundle._diagnostics_compressed is True

    def test_to_dict_decompresses(self, service):
        """to_dict decompresses all fields."""
        large_snapshot = {"data": "x" * COMPRESSION_THRESHOLD * 2}
        bundle = service.create_bundle(
            task_id="task-001",
            purpose="continue_work",
            rebuild_level="L1",
            state_snapshot=large_snapshot,
        )
        result = bundle.to_dict()
        assert result["state_snapshot"] == large_snapshot


class TestCaching:
    """Test LRU cache for latest bundle."""

    def test_get_latest_bundle_caches(self, service):
        """get_latest_bundle caches result."""
        # Create two bundles
        service.create_bundle(
            task_id="task-001",
            purpose="continue_work",
            rebuild_level="L1",
            state_snapshot={"v": 1},
        )
        service.create_bundle(
            task_id="task-001",
            purpose="continue_work",
            rebuild_level="L1",
            state_snapshot={"v": 2},
        )

        # Get latest (should cache)
        bundle1 = service.get_latest_bundle("task-001")
        assert bundle1 is not None
        assert "task-001" in service._latest_cache

        # Second call should use cache
        bundle2 = service.get_latest_bundle("task-001")
        assert bundle2.id == bundle1.id

    def test_cache_invalidation_on_create(self, service):
        """Creating new bundle invalidates cache."""
        service.create_bundle(
            task_id="task-001",
            purpose="continue_work",
            rebuild_level="L1",
            state_snapshot={"v": 1},
        )
        service.get_latest_bundle("task-001")
        assert "task-001" in service._latest_cache

        # Create new bundle
        service.create_bundle(
            task_id="task-001",
            purpose="continue_work",
            rebuild_level="L1",
            state_snapshot={"v": 2},
        )

        # Cache should be invalidated
        assert "task-001" not in service._latest_cache

    def test_cache_size_limit(self, service):
        """Cache respects max size."""
        service._cache_max_size = 3

        # Create bundles for multiple tasks (skip task-001 which fixture already has)
        for i in range(2, 6):
            task_id = f"task-{i:03d}"
            service.conn.execute(
                "INSERT INTO task (id, title, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (task_id, f"Task {i}", "proposed", "2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z"),
            )
            service.create_bundle(
                task_id=task_id,
                purpose="continue_work",
                rebuild_level="L1",
                state_snapshot={"v": i},
            )
            service.get_latest_bundle(task_id)

        # Cache should have at most 3 entries
        assert len(service._latest_cache) <= 3

    def test_clear_cache(self, service):
        """clear_cache removes all cached entries."""
        service.create_bundle(
            task_id="task-001",
            purpose="continue_work",
            rebuild_level="L1",
            state_snapshot={"v": 1},
        )
        service.get_latest_bundle("task-001")
        assert len(service._latest_cache) > 0

        service.clear_cache()
        assert len(service._latest_cache) == 0


class TestDifferentialBundle:
    """Test differential bundle creation."""

    def test_create_bundle_with_diff(self, service):
        """create_bundle with use_diff computes differential."""
        # Create first bundle
        service.create_bundle(
            task_id="task-001",
            purpose="continue_work",
            rebuild_level="L1",
            state_snapshot={"status": "in_progress", "goal": "Build feature"},
        )

        # Create second bundle with diff
        bundle2 = service.create_bundle(
            task_id="task-001",
            purpose="continue_work",
            rebuild_level="L1",
            state_snapshot={"status": "review", "goal": "Build feature"},
            use_diff=True,
        )

        # The second bundle should contain only the changed field
        snapshot = decompress_json(
            bundle2.state_snapshot_json,
            bundle2._state_snapshot_compressed
        )
        assert snapshot == {"status": "review"}

    def test_create_bundle_diff_no_previous(self, service):
        """use_diff with no previous bundle uses full snapshot."""
        bundle = service.create_bundle(
            task_id="task-001",
            purpose="continue_work",
            rebuild_level="L1",
            state_snapshot={"status": "in_progress"},
            use_diff=True,
        )
        snapshot = decompress_json(
            bundle.state_snapshot_json,
            bundle._state_snapshot_compressed
        )
        assert snapshot == {"status": "in_progress"}
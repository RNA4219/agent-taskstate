"""Tests for TrackerResolver and MemxResolver."""

import pytest
import sqlite3
from pathlib import Path

from src.resolver import (
    ContextRebuildResolver,
    TrackerResolver,
    MemxResolver,
    ResolveStatus,
    ResolvedRef,
    ResolverDiagnostics,
    AgentTaskstateLocalResolver,
)
from src.typed_ref import tracker_ref, memx_ref, agent_taskstate_ref, format_ref, parse_ref
from src.tracker_bridge import (
    TrackerBridgeService,
    MockTrackerAdapter,
    create_tracker_tables,
)


@pytest.fixture
def conn():
    """Create in-memory database."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    # Create task table
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
    conn.execute("""
        INSERT INTO task (id, title, status, created_at, updated_at)
        VALUES ('task-001', 'Test Task', 'in_progress', '2024-01-01T00:00:00Z', '2024-01-01T00:00:00Z')
    """)
    yield conn
    conn.close()


class TestTrackerResolver:
    """Test TrackerResolver class."""

    def test_tracker_resolver_init(self):
        """TrackerResolver initializes without adapters."""
        resolver = TrackerResolver()
        assert resolver is not None

    def test_tracker_resolver_init_with_adapters(self):
        """TrackerResolver initializes with adapters."""
        adapters = {"mock": MockTrackerAdapter()}
        resolver = TrackerResolver(adapters=adapters)
        assert resolver is not None

    def test_tracker_resolver_can_resolve_tracker_refs(self):
        """TrackerResolver handles tracker:issue refs."""
        resolver = TrackerResolver()
        ref = tracker_ref("issue", "issue-123", "github")
        assert resolver.can_resolve(ref) is True

    def test_tracker_resolver_cannot_resolve_other_domains(self):
        """TrackerResolver rejects non-tracker refs."""
        resolver = TrackerResolver()
        ref = memx_ref("evidence", "ev-001")
        assert resolver.can_resolve(ref) is False
        ref2 = agent_taskstate_ref("task", "task-001")
        assert resolver.can_resolve(ref2) is False


class TestMemxResolver:
    """Test MemxResolver class."""

    def test_memx_resolver_init(self):
        """MemxResolver initializes."""
        resolver = MemxResolver()
        assert resolver is not None

    def test_memx_resolver_can_resolve_memx_refs(self):
        """MemxResolver handles memx refs."""
        resolver = MemxResolver()
        ref = memx_ref("evidence", "ev-001")
        assert resolver.can_resolve(ref) is True

    def test_memx_resolver_cannot_resolve_other_domains(self):
        """MemxResolver rejects non-memx refs."""
        resolver = MemxResolver()
        ref = tracker_ref("issue", "issue-123", "github")
        assert resolver.can_resolve(ref) is False
        ref2 = agent_taskstate_ref("task", "task-001")
        assert resolver.can_resolve(ref2) is False


class TestAgentTaskstateLocalResolver:
    """Test AgentTaskstateLocalResolver (already tested in existing tests)."""

    def test_resolver_init(self):
        """AgentTaskstateLocalResolver initializes."""
        resolver = AgentTaskstateLocalResolver()
        assert resolver is not None

    def test_resolver_can_resolve_agent_taskstate_refs(self):
        """AgentTaskstateLocalResolver handles agent-taskstate refs."""
        resolver = AgentTaskstateLocalResolver()
        ref = agent_taskstate_ref("task", "task-001")
        assert resolver.can_resolve(ref) is True

    def test_resolver_cannot_resolve_other_domains(self):
        """AgentTaskstateLocalResolver rejects non-agent-taskstate refs."""
        resolver = AgentTaskstateLocalResolver()
        ref = tracker_ref("issue", "issue-123", "github")
        assert resolver.can_resolve(ref) is False
        ref2 = memx_ref("evidence", "ev-001")
        assert resolver.can_resolve(ref2) is False


class TestTypedRefFormats:
    """Test typed_ref format functions."""

    def test_tracker_ref_format(self):
        """tracker_ref produces correct format."""
        ref = tracker_ref("issue", "issue-123", "github")
        parsed = parse_ref(ref)
        assert parsed.domain == "tracker"
        assert parsed.entity_type == "issue"
        assert parsed.provider == "github"
        assert parsed.entity_id == "issue-123"

    def test_memx_ref_format(self):
        """memx_ref produces correct format."""
        ref = memx_ref("evidence", "ev-001")
        parsed = parse_ref(ref)
        assert parsed.domain == "memx"
        assert parsed.entity_type == "evidence"
        assert parsed.provider == "local"
        assert parsed.entity_id == "ev-001"


class TestMockTrackerAdapter:
    """Test MockTrackerAdapter for testing."""

    def test_mock_adapter_init(self):
        """MockTrackerAdapter initializes."""
        adapter = MockTrackerAdapter()
        assert adapter is not None

    def test_mock_adapter_has_fetch_issue(self):
        """MockTrackerAdapter has fetch_issue method."""
        adapter = MockTrackerAdapter()
        assert hasattr(adapter, "fetch_issue")

    def test_mock_adapter_has_post_comment(self):
        """MockTrackerAdapter has post_comment method."""
        adapter = MockTrackerAdapter()
        assert hasattr(adapter, "post_comment")


class TestTrackerBridgeService:
    """Test TrackerBridgeService functionality."""

    def test_tracker_bridge_service_init(self, conn):
        """TrackerBridgeService initializes."""
        create_tracker_tables(conn)
        service = TrackerBridgeService(conn)
        assert service is not None

    def test_tracker_bridge_service_default_adapter(self, conn):
        """TrackerBridgeService uses default adapter."""
        create_tracker_tables(conn)
        service = TrackerBridgeService(conn)
        assert service is not None

    def test_tracker_bridge_create_connection(self, conn):
        """TrackerBridgeService creates connection."""
        create_tracker_tables(conn)
        service = TrackerBridgeService(conn)
        conn_rec = service.create_connection(
            name="github-main",
            provider="github",
            config={"token": "test"},
        )
        assert conn_rec is not None
        assert conn_rec.name == "github-main"


class TestResolveStatus:
    """Test ResolveStatus enum."""

    def test_resolve_status_members(self):
        """ResolveStatus has expected members."""
        assert ResolveStatus.RESOLVED.name == "RESOLVED"
        assert ResolveStatus.UNRESOLVED.name == "UNRESOLVED"
        assert ResolveStatus.UNSUPPORTED.name == "UNSUPPORTED"


class TestResolverDiagnostics:
    """Test ResolverDiagnostics."""

    def test_resolver_diagnostics_defaults(self):
        """ResolverDiagnostics has default values."""
        diag = ResolverDiagnostics()
        # Check expected fields
        assert hasattr(diag, "missing_refs")
        assert hasattr(diag, "unsupported_refs")
        assert hasattr(diag, "resolver_warnings")
        assert hasattr(diag, "partial_bundle")
        assert diag.missing_refs == []
        assert diag.unsupported_refs == []
        assert diag.partial_bundle is False

    def test_resolver_diagnostics_to_dict_exists(self):
        """ResolverDiagnostics has to_dict method."""
        diag = ResolverDiagnostics()
        assert hasattr(diag, "to_dict")
        data = diag.to_dict()
        assert isinstance(data, dict)
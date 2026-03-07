"""
Tests for resolver module.

Covers:
- ResolveRef / ResolveMany
- summary-first retrieval
- diagnostics
- raw descent conditions
"""

import pytest
import sqlite3

from src.resolver import (
    ContextRebuildResolver,
    ResolveStatus,
    ResolvedRef,
    ResolveReport,
    SummaryPayload,
    RawPayload,
    ResolverDiagnostics,
    AgentTaskstateLocalResolver,
    RAW_DESCENT_CONDITIONS,
)


@pytest.fixture
def conn():
    """Create an in-memory database with test data."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    # Create tables
    conn.execute("""
        CREATE TABLE task (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            status TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE decision (
            id TEXT PRIMARY KEY,
            summary TEXT NOT NULL,
            status TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE context_bundle (
            id TEXT PRIMARY KEY,
            purpose TEXT NOT NULL,
            summary TEXT
        )
    """)

    # Insert test data
    conn.execute(
        "INSERT INTO task (id, title, status) VALUES (?, ?, ?)",
        ("task_001", "Test Task", "in_progress"),
    )
    conn.execute(
        "INSERT INTO decision (id, summary, status) VALUES (?, ?, ?)",
        ("dec_001", "Use PostgreSQL for storage", "accepted"),
    )
    conn.execute(
        "INSERT INTO context_bundle (id, purpose, summary) VALUES (?, ?, ?)",
        ("bundle_001", "continue_work", "Test bundle summary"),
    )

    yield conn
    conn.close()


@pytest.fixture
def agent_taskstate_resolver(conn):
    """Create a AgentTaskstateLocalResolver with DB connection."""
    return AgentTaskstateLocalResolver(conn)


@pytest.fixture
def resolver(agent_taskstate_resolver):
    """Create a ContextRebuildResolver with AgentTaskstateLocalResolver registered."""
    resolver = ContextRebuildResolver()
    resolver.register_resolver(agent_taskstate_resolver)
    return resolver


class TestResolveStatus:
    """Test ResolveStatus enum."""

    def test_status_values(self):
        """Status enum has expected values."""
        assert ResolveStatus.RESOLVED.value == "resolved"
        assert ResolveStatus.UNRESOLVED.value == "unresolved"
        assert ResolveStatus.UNSUPPORTED.value == "unsupported"


class TestResolvedRef:
    """Test ResolvedRef dataclass."""

    def test_resolved_ref(self):
        """Create a resolved ref."""
        ref = ResolvedRef(
            ref="agent-taskstate:task:local:task_001",
            status=ResolveStatus.RESOLVED,
            summary="Test Task",
            metadata={"status": "in_progress"},
        )
        assert ref.status == ResolveStatus.RESOLVED
        assert ref.summary == "Test Task"
        assert ref.raw_available is False


class TestResolveReport:
    """Test ResolveReport dataclass."""

    def test_empty_report(self):
        """Empty report has zero count."""
        report = ResolveReport()
        assert report.total_count == 0
        assert report.success_rate == 1.0

    def test_report_with_results(self):
        """Report with mixed results."""
        report = ResolveReport(
            resolved=[ResolvedRef("ref1", ResolveStatus.RESOLVED)],
            unresolved=[ResolvedRef("ref2", ResolveStatus.UNRESOLVED)],
            unsupported=[ResolvedRef("ref3", ResolveStatus.UNSUPPORTED)],
        )
        assert report.total_count == 3
        assert report.success_rate == 1 / 3


class TestResolverDiagnostics:
    """Test ResolverDiagnostics dataclass."""

    def test_empty_diagnostics(self):
        """Empty diagnostics."""
        diag = ResolverDiagnostics()
        assert diag.missing_refs == []
        assert diag.partial_bundle is False

    def test_diagnostics_to_dict(self):
        """Diagnostics serialization."""
        diag = ResolverDiagnostics(
            missing_refs=["ref1"],
            unsupported_refs=["ref2"],
            resolver_warnings=["Warning 1"],
            partial_bundle=True,
        )
        result = diag.to_dict()
        assert result["missing_refs"] == ["ref1"]
        assert result["partial_bundle"] is True


class TestAgentTaskstateLocalResolver:
    """Test AgentTaskstateLocalResolver."""

    def test_can_resolve_agent_taskstate_local(self, agent_taskstate_resolver):
        """Can resolve agent-taskstate local refs."""
        assert agent_taskstate_resolver.can_resolve("agent-taskstate:task:local:task_001") is True
        assert agent_taskstate_resolver.can_resolve("agent-taskstate:decision:local:dec_001") is True

    def test_cannot_resolve_other_domains(self, agent_taskstate_resolver):
        """Cannot resolve other domains."""
        assert agent_taskstate_resolver.can_resolve("memx:evidence:local:ev_001") is False
        assert agent_taskstate_resolver.can_resolve("tracker:issue:jira:PROJ-123") is False

    def test_resolve_existing_task(self, agent_taskstate_resolver):
        """Resolve an existing task."""
        result = agent_taskstate_resolver.resolve("agent-taskstate:task:local:task_001")
        assert result.status == ResolveStatus.RESOLVED
        assert result.summary == "Test Task"
        assert result.metadata["status"] == "in_progress"

    def test_resolve_nonexistent_task(self, agent_taskstate_resolver):
        """Resolve a nonexistent task."""
        result = agent_taskstate_resolver.resolve("agent-taskstate:task:local:nonexistent")
        assert result.status == ResolveStatus.UNRESOLVED
        assert "not found" in result.error_message.lower()

    def test_resolve_existing_decision(self, agent_taskstate_resolver):
        """Resolve an existing decision."""
        result = agent_taskstate_resolver.resolve("agent-taskstate:decision:local:dec_001")
        assert result.status == ResolveStatus.RESOLVED
        assert result.summary == "Use PostgreSQL for storage"

    def test_resolve_existing_bundle(self, agent_taskstate_resolver):
        """Resolve an existing context bundle."""
        result = agent_taskstate_resolver.resolve("agent-taskstate:context_bundle:local:bundle_001")
        assert result.status == ResolveStatus.RESOLVED
        assert result.summary == "Test bundle summary"

    def test_resolve_without_db(self):
        """Resolve without DB connection returns unresolved."""
        resolver = AgentTaskstateLocalResolver(conn=None)
        result = resolver.resolve("agent-taskstate:task:local:task_001")
        assert result.status == ResolveStatus.UNRESOLVED
        assert "database" in result.error_message.lower()


class TestContextRebuildResolver:
    """Test ContextRebuildResolver."""

    def test_resolve_ref(self, resolver):
        """Resolve a single ref."""
        result = resolver.resolve_ref("agent-taskstate:task:local:task_001")
        assert result.status == ResolveStatus.RESOLVED

    def test_resolve_unsupported_domain(self, resolver):
        """Resolve an unsupported domain."""
        result = resolver.resolve_ref("unknown:entity:local:id")
        assert result.status == ResolveStatus.UNSUPPORTED

    def test_resolve_many(self, resolver):
        """Resolve multiple refs."""
        refs = [
            "agent-taskstate:task:local:task_001",
            "agent-taskstate:decision:local:dec_001",
            "agent-taskstate:task:local:nonexistent",
            "memx:evidence:local:ev_001",
        ]
        report = resolver.resolve_many(refs)

        assert len(report.resolved) == 2
        assert len(report.unresolved) == 1
        assert len(report.unsupported) == 1

    def test_load_summary(self, resolver):
        """Load summary for a ref."""
        summary = resolver.load_summary("agent-taskstate:task:local:task_001")
        assert summary is not None
        assert summary.summary == "Test Task"

    def test_load_summary_nonexistent(self, resolver):
        """Load summary for nonexistent ref returns None."""
        summary = resolver.load_summary("agent-taskstate:task:local:nonexistent")
        assert summary is None

    def test_load_selected_raw(self, resolver):
        """Load raw content for a ref."""
        raw = resolver.load_selected_raw("agent-taskstate:task:local:task_001")
        assert raw is not None
        assert raw.content == "Test Task"

    def test_get_diagnostics(self, resolver):
        """Generate diagnostics from resolve report."""
        report = resolver.resolve_many([
            "agent-taskstate:task:local:task_001",
            "agent-taskstate:task:local:nonexistent",
            "memx:evidence:local:ev_001",
        ])
        diag = resolver.get_diagnostics(report)

        assert len(diag.missing_refs) == 1
        assert len(diag.unsupported_refs) == 1
        assert diag.partial_bundle is True


class TestRawDescentConditions:
    """Test raw descent conditions."""

    def test_raw_descent_conditions_defined(self):
        """Raw descent conditions are defined."""
        assert "before_review" in RAW_DESCENT_CONDITIONS
        assert "high_priority_open_question" in RAW_DESCENT_CONDITIONS
        assert "operator_request" in RAW_DESCENT_CONDITIONS

    def test_should_include_raw_operator_request(self, resolver):
        """Operator request always includes raw."""
        assert resolver.should_include_raw("operator_request") is True

    def test_should_include_raw_with_context(self, resolver):
        """Raw inclusion with task context."""
        assert resolver.should_include_raw(
            "high_priority_open_question",
            {"has_high_priority_questions": True}
        ) is True

        assert resolver.should_include_raw(
            "high_priority_open_question",
            {"has_high_priority_questions": False}
        ) is False

    def test_should_not_include_raw_invalid_condition(self, resolver):
        """Invalid condition returns False."""
        assert resolver.should_include_raw("invalid_condition") is False


class TestIntegration:
    """Integration tests for P3 requirements."""

    def test_summary_first_retrieval(self, resolver):
        """Summary-first retrieval returns summary."""
        summary = resolver.load_summary("agent-taskstate:task:local:task_001")
        assert summary is not None
        assert isinstance(summary, SummaryPayload)

    def test_bundle_continues_on_unresolved(self, resolver):
        """Bundle build continues even with unresolved refs."""
        report = resolver.resolve_many([
            "agent-taskstate:task:local:task_001",
            "agent-taskstate:task:local:nonexistent",
            "memx:evidence:local:ev_001",
        ])

        # At least one resolved
        assert len(report.resolved) >= 1
        # Has diagnostics
        diag = resolver.get_diagnostics(report)
        assert diag.partial_bundle is True

    def test_source_refs_traceable(self, resolver):
        """Source refs can be traced back."""
        result = resolver.resolve_ref("agent-taskstate:task:local:task_001")
        assert result.status == ResolveStatus.RESOLVED
        assert result.ref == "agent-taskstate:task:local:task_001"
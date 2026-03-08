"""
Tests for tracker_bridge module.

Covers:
- Issue fetch and cache
- Entity linking
- Sync event tracking
- Snapshot export
- Outbound operations
"""

import sqlite3

import pytest

from src.tracker_bridge import (
    EntityLink,
    IssueCache,
    IssueSnapshot,
    LinkRole,
    MockTrackerAdapter,
    SyncDirection,
    SyncEvent,
    SyncStatus,
    SyncSuggestion,
    TrackerBridgeService,
    TrackerConnection,
    create_tracker_tables,
)


@pytest.fixture
def conn():
    """Create an in-memory database with tracker tables."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_tracker_tables(conn)
    yield conn
    conn.close()


@pytest.fixture
def mock_adapter():
    """Create a mock tracker adapter with test data."""
    return MockTrackerAdapter(
        {
            "PROJ-123": {
                "key": "PROJ-123",
                "summary": "Test Issue",
                "status": "In Progress",
                "assignee": "user@example.com",
                "description": "Test description",
            },
            "PROJ-456": {
                "key": "PROJ-456",
                "summary": "Another Issue",
                "status": "Done",
                "assignee": None,
                "description": None,
            },
        }
    )


@pytest.fixture
def service(conn, mock_adapter):
    """Create a TrackerBridgeService with mock adapter."""
    service = TrackerBridgeService(conn)
    service.register_adapter("jira", mock_adapter)
    return service


@pytest.fixture
def connection(service):
    """Create a test tracker connection."""
    return service.create_connection(
        provider="jira",
        name="Test Jira",
        config={"url": "https://example.atlassian.net"},
    )


class TestEnums:
    """Test enum values."""

    def test_sync_direction(self):
        assert SyncDirection.INBOUND.value == "inbound"
        assert SyncDirection.OUTBOUND.value == "outbound"

    def test_sync_status(self):
        assert SyncStatus.SUCCESS.value == "success"
        assert SyncStatus.FAILED.value == "failed"

    def test_link_role(self):
        assert LinkRole.PRIMARY.value == "primary"
        assert LinkRole.RELATED.value == "related"
        assert LinkRole.BLOCKS.value == "blocks"


class TestTrackerConnection:
    """Test TrackerConnection."""

    def test_create_connection(self, service):
        conn = service.create_connection(
            provider="jira",
            name="My Jira",
            config={"url": "https://test.atlassian.net"},
        )

        assert conn.id is not None
        assert conn.provider == "jira"
        assert conn.name == "My Jira"


class TestIssueFetch:
    """Test issue fetching and caching."""

    def test_fetch_issue(self, service, connection):
        issue = service.fetch_issue(connection.id, "PROJ-123")

        assert issue is not None
        assert issue.remote_key == "PROJ-123"
        assert issue.title == "Test Issue"
        assert issue.status == "In Progress"
        assert issue.issue_ref == "tracker:issue:jira:PROJ-123"

    def test_fetch_nonexistent_issue(self, service, connection):
        issue = service.fetch_issue(connection.id, "NONEXISTENT")
        assert issue is None

        events = service.get_sync_events()
        assert len(events) == 1
        assert events[0].status == "failed"

    def test_fetch_records_sync_event(self, service, connection):
        service.fetch_issue(connection.id, "PROJ-123")

        events = service.get_sync_events()
        assert len(events) == 1
        assert events[0].direction == "inbound"
        assert events[0].status == "success"


class TestEntityLinking:
    """Test entity linking."""

    def test_link_issue_to_task(self, service, connection):
        service.fetch_issue(connection.id, "PROJ-123")

        link = service.link_issue_to_task(
            issue_ref="tracker:issue:jira:PROJ-123",
            task_ref="agent-taskstate:task:local:task_001",
            role="primary",
        )

        assert link.tracker_issue_ref == "tracker:issue:jira:PROJ-123"
        assert link.agent_taskstate_entity_ref == "agent-taskstate:task:local:task_001"
        assert link.role == "primary"

    def test_link_issue_to_task_rejects_invalid_refs(self, service, connection):
        service.fetch_issue(connection.id, "PROJ-123")

        with pytest.raises(ValueError, match="agent-taskstate local task"):
            service.link_issue_to_task(
                issue_ref="tracker:issue:jira:PROJ-123",
                task_ref="agent_taskstate:task:local:task_001",
            )

    def test_get_issue_links(self, service, connection):
        service.fetch_issue(connection.id, "PROJ-123")
        service.link_issue_to_task(
            "tracker:issue:jira:PROJ-123",
            "agent-taskstate:task:local:task_001",
            "primary",
        )
        service.link_issue_to_task(
            "tracker:issue:jira:PROJ-123",
            "agent-taskstate:task:local:task_002",
            "related",
        )

        links = service.get_issue_links("tracker:issue:jira:PROJ-123")
        assert len(links) == 2

    def test_get_task_links(self, service, connection):
        service.fetch_issue(connection.id, "PROJ-123")
        service.link_issue_to_task(
            "tracker:issue:jira:PROJ-123",
            "agent-taskstate:task:local:task_001",
            "primary",
        )

        links = service.get_task_links("agent-taskstate:task:local:task_001")
        assert len(links) == 1
        assert links[0].tracker_issue_ref == "tracker:issue:jira:PROJ-123"


class TestIssueSnapshot:
    """Test issue snapshot for context build."""

    def test_get_issue_snapshot(self, service, connection):
        service.fetch_issue(connection.id, "PROJ-123")

        snapshot = service.get_issue_snapshot("tracker:issue:jira:PROJ-123")

        assert snapshot is not None
        assert snapshot.remote_key == "PROJ-123"
        assert snapshot.title == "Test Issue"

    def test_snapshot_to_dict(self, service, connection):
        service.fetch_issue(connection.id, "PROJ-123")
        snapshot = service.get_issue_snapshot("tracker:issue:jira:PROJ-123")

        result = snapshot.to_dict()

        assert result["remote_key"] == "PROJ-123"
        assert result["title"] == "Test Issue"
        assert "issue_ref" in result

    def test_snapshot_uses_latest_sync_status(self, service, connection):
        service.fetch_issue(connection.id, "PROJ-123")
        service.update_outbound_status(connection.id, "PROJ-123", "Done")

        snapshot = service.get_issue_snapshot("tracker:issue:jira:PROJ-123")
        assert snapshot is not None
        assert snapshot.last_sync_result == "success"

    def test_snapshot_nonexistent(self, service):
        snapshot = service.get_issue_snapshot("tracker:issue:jira:NONEXISTENT")
        assert snapshot is None


class TestSyncEvents:
    """Test sync event tracking."""

    def test_get_sync_events(self, service, connection):
        service.fetch_issue(connection.id, "PROJ-123")
        service.fetch_issue(connection.id, "PROJ-456")

        events = service.get_sync_events()
        assert len(events) == 2

    def test_filter_by_connection(self, service, connection):
        service.fetch_issue(connection.id, "PROJ-123")

        events = service.get_sync_events(connection_id=connection.id)
        assert len(events) == 1

    def test_filter_by_issue(self, service, connection):
        service.fetch_issue(connection.id, "PROJ-123")
        service.fetch_issue(connection.id, "PROJ-456")

        events = service.get_sync_events(issue_ref="tracker:issue:jira:PROJ-123")
        assert len(events) == 1


class TestOutboundOperations:
    """Test outbound operations."""

    def test_post_comment(self, service, connection):
        result = service.post_outbound_comment(
            connection_id=connection.id,
            issue_key="PROJ-123",
            comment="Status updated in agent-taskstate",
        )

        assert result is True

        events = service.get_sync_events()
        outbound = [e for e in events if e.direction == "outbound"]
        assert len(outbound) == 1

    def test_update_outbound_status(self, service, connection):
        result = service.update_outbound_status(
            connection_id=connection.id,
            issue_key="PROJ-123",
            status="Done",
        )

        assert result is True

        events = service.get_sync_events()
        outbound = [e for e in events if e.direction == "outbound"]
        assert len(outbound) == 1
        assert outbound[0].details_json is not None
        assert "update_status" in outbound[0].details_json


class TestSyncSuggestions:
    """Test sync suggestions."""

    def test_generate_suggestions(self, service, connection):
        service.fetch_issue(connection.id, "PROJ-123")
        service.link_issue_to_task(
            "tracker:issue:jira:PROJ-123",
            "agent-taskstate:task:local:task_001",
            "primary",
        )

        suggestions = service.generate_sync_suggestions("tracker:issue:jira:PROJ-123")

        assert len(suggestions) >= 1
        assert suggestions[0].requires_confirmation is True
        assert suggestions[0].agent_taskstate_task_ref == "agent-taskstate:task:local:task_001"

    def test_suggestions_no_links(self, service, connection):
        service.fetch_issue(connection.id, "PROJ-123")

        suggestions = service.generate_sync_suggestions("tracker:issue:jira:PROJ-123")

        assert len(suggestions) == 0


class TestIntegration:
    """Integration tests for P4 requirements."""

    def test_issue_fetch_and_cache(self, service, connection):
        issue = service.fetch_issue(connection.id, "PROJ-123")

        assert issue is not None
        assert issue.issue_ref == "tracker:issue:jira:PROJ-123"

    def test_issue_task_linking(self, service, connection):
        service.fetch_issue(connection.id, "PROJ-123")
        link = service.link_issue_to_task(
            "tracker:issue:jira:PROJ-123",
            "agent-taskstate:task:local:task_001",
        )

        assert link.tracker_issue_ref == "tracker:issue:jira:PROJ-123"
        assert link.agent_taskstate_entity_ref == "agent-taskstate:task:local:task_001"

    def test_sync_event_tracking(self, service, connection):
        service.fetch_issue(connection.id, "PROJ-123")
        service.post_outbound_comment(connection.id, "PROJ-123", "Update")

        events = service.get_sync_events()
        assert len(events) == 2
        directions = [e.direction for e in events]
        assert "inbound" in directions
        assert "outbound" in directions

    def test_snapshot_for_context_build(self, service, connection):
        service.fetch_issue(connection.id, "PROJ-123")
        snapshot = service.get_issue_snapshot("tracker:issue:jira:PROJ-123")

        assert snapshot is not None
        snapshot_dict = snapshot.to_dict()
        assert "remote_key" in snapshot_dict
        assert "title" in snapshot_dict

    def test_agent_taskstate_continues_without_tracker(self, service, connection):
        service.fetch_issue(connection.id, "PROJ-123")
        snapshot = service.get_issue_snapshot("tracker:issue:jira:PROJ-123")
        assert snapshot is not None

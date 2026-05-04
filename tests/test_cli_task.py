"""Tests for CLI task commands."""

import json
import pytest
import tempfile
from pathlib import Path

from cli import main
from cli.db import connect, init_db
from cli.utils import now_utc


@pytest.fixture
def tmp_db():
    """Create temporary database file."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    yield path
    Path(path).unlink(missing_ok=True)


@pytest.fixture
def setup_db(tmp_db):
    """Initialize database and create test task."""
    main(["--db", tmp_db, "init"])
    # Create a test task
    payload = {
        "id": "task-001",
        "kind": "feature",
        "title": "Test Task",
        "goal": "Build feature",
        "status": "draft",
        "priority": "high",
        "owner_type": "agent",
        "owner_id": "agent-001",
    }
    main(["--db", tmp_db, "task", "create", "--json", json.dumps(payload)])
    yield tmp_db


class TestTaskCreate:
    """Test task create command."""

    def test_create_task_minimal(self, tmp_db):
        """Create task with minimal fields."""
        main(["--db", tmp_db, "init"])
        payload = {"kind": "feature", "title": "Test", "goal": "Goal"}
        result = main(["--db", tmp_db, "task", "create", "--json", json.dumps(payload)])
        assert result == 0

    def test_create_task_full(self, tmp_db):
        """Create task with all fields."""
        main(["--db", tmp_db, "init"])
        payload = {
            "id": "task-002",
            "kind": "bugfix",
            "title": "Fix bug",
            "goal": "Fix critical bug",
            "status": "ready",
            "priority": "high",
            "owner_type": "human",
            "owner_id": "user-001",
            "idempotency_key": "key-001",
        }
        result = main(["--db", tmp_db, "task", "create", "--json", json.dumps(payload)])
        assert result == 0

    def test_create_task_with_parent(self, setup_db):
        """Create task with parent_task_id."""
        payload = {
            "id": "task-child",
            "parent_task_id": "task-001",
            "kind": "feature",
            "title": "Child task",
            "goal": "Sub-goal",
        }
        result = main(["--db", setup_db, "task", "create", "--json", json.dumps(payload)])
        assert result == 0

    def test_create_task_invalid_kind(self, setup_db):
        """Invalid kind returns error."""
        payload = {"kind": "invalid_kind", "title": "Test", "goal": "Goal"}
        result = main(["--db", setup_db, "task", "create", "--json", json.dumps(payload)])
        assert result != 0

    def test_create_task_invalid_status(self, setup_db):
        """Invalid status returns error."""
        payload = {"kind": "feature", "title": "Test", "goal": "Goal", "status": "invalid"}
        result = main(["--db", setup_db, "task", "create", "--json", json.dumps(payload)])
        assert result != 0

    def test_create_task_from_file(self, tmp_db):
        """Create task from JSON file."""
        main(["--db", tmp_db, "init"])
        payload = {"kind": "feature", "title": "FromFile", "goal": "Goal"}
        json_file = tmp_db + ".json"
        with open(json_file, "w") as f:
            json.dump(payload, f)
        result = main(["--db", tmp_db, "task", "create", "--file", json_file])
        assert result == 0
        Path(json_file).unlink()


class TestTaskShow:
    """Test task show command."""

    def test_show_task(self, setup_db):
        """Show existing task."""
        result = main(["--db", setup_db, "task", "show", "--task", "task-001"])
        assert result == 0

    def test_show_nonexistent_task(self, setup_db):
        """Show nonexistent task returns error."""
        result = main(["--db", setup_db, "task", "show", "--task", "nonexistent"])
        assert result != 0


class TestTaskList:
    """Test task list command."""

    def test_list_all_tasks(self, setup_db):
        """List all tasks."""
        result = main(["--db", setup_db, "task", "list"])
        assert result == 0

    def test_list_filter_by_status(self, setup_db):
        """List tasks by status."""
        result = main(["--db", setup_db, "task", "list", "--status", "draft"])
        assert result == 0

    def test_list_filter_by_kind(self, setup_db):
        """List tasks by kind."""
        result = main(["--db", setup_db, "task", "list", "--kind", "feature"])
        assert result == 0

    def test_list_filter_by_owner_type(self, setup_db):
        """List tasks by owner_type."""
        result = main(["--db", setup_db, "task", "list", "--owner-type", "agent"])
        assert result == 0

    def test_list_filter_by_priority(self, setup_db):
        """List tasks by priority."""
        result = main(["--db", setup_db, "task", "list", "--priority", "high"])
        assert result == 0

    def test_list_multiple_filters(self, setup_db):
        """List with multiple filters."""
        result = main([
            "--db", setup_db, "task", "list",
            "--status", "draft",
            "--kind", "feature",
            "--priority", "high",
        ])
        assert result == 0


class TestTaskUpdate:
    """Test task update command."""

    def test_update_task_title(self, setup_db):
        """Update task title."""
        payload = {"title": "Updated Title"}
        result = main(["--db", setup_db, "task", "update", "--task", "task-001", "--json", json.dumps(payload)])
        assert result == 0

    def test_update_task_priority(self, setup_db):
        """Update task priority."""
        payload = {"priority": "low"}
        result = main(["--db", setup_db, "task", "update", "--task", "task-001", "--json", json.dumps(payload)])
        assert result == 0

    def test_update_task_invalid_priority(self, setup_db):
        """Invalid priority returns error."""
        payload = {"priority": "invalid"}
        result = main(["--db", setup_db, "task", "update", "--task", "task-001", "--json", json.dumps(payload)])
        assert result != 0

    def test_update_task_no_fields(self, setup_db):
        """No updatable fields returns error."""
        payload = {"invalid_field": "value"}
        result = main(["--db", setup_db, "task", "update", "--task", "task-001", "--json", json.dumps(payload)])
        assert result != 0

    def test_update_nonexistent_task(self, setup_db):
        """Update nonexistent task returns error."""
        payload = {"title": "New Title"}
        result = main(["--db", setup_db, "task", "update", "--task", "nonexistent", "--json", json.dumps(payload)])
        assert result != 0


class TestTaskSetStatus:
    """Test task set-status command."""

    def test_set_status_draft_to_ready_requires_done_when(self, setup_db):
        """Transition draft to ready requires done_when."""
        # Try to move to ready without state - should fail
        result = main([
            "--db", setup_db, "task", "set-status",
            "--task", "task-001",
            "--to", "ready",
        ])
        assert result != 0  # Requires done_when in state

    def test_set_status_with_state_and_done_when(self, setup_db):
        """Set status with proper state."""
        # First create state with done_when
        state_payload = {
            "current_step": "start",
            "constraints": [],
            "done_when": [{"description": "Complete", "done": False}],
            "artifact_refs": [],
            "evidence_refs": [],
            "context_policy": {},
            "confidence": "medium",
        }
        main(["--db", setup_db, "state", "put", "--task", "task-001", "--json", json.dumps(state_payload)])
        # Now move to ready
        result = main([
            "--db", setup_db, "task", "set-status",
            "--task", "task-001",
            "--to", "ready",
        ])
        assert result == 0

    def test_set_status_to_in_progress_with_reason(self, setup_db):
        """Set status to in_progress with reason."""
        # Setup: create state, move to ready
        state_payload = {
            "current_step": "start",
            "constraints": [],
            "done_when": [{"description": "Complete", "done": False}],
            "artifact_refs": [],
            "evidence_refs": [],
            "context_policy": {},
            "confidence": "medium",
        }
        main(["--db", setup_db, "state", "put", "--task", "task-001", "--json", json.dumps(state_payload)])
        main(["--db", setup_db, "task", "set-status", "--task", "task-001", "--to", "ready"])
        # Then to in_progress with reason
        result = main([
            "--db", setup_db, "task", "set-status",
            "--task", "task-001",
            "--to", "in_progress",
            "--reason", "Starting work",
        ])
        assert result == 0

    def test_set_status_invalid_transition(self, setup_db):
        """Invalid transition returns error."""
        # Try draft -> done (not allowed)
        result = main([
            "--db", setup_db, "task", "set-status",
            "--task", "task-001",
            "--to", "done",
        ])
        assert result != 0

    def test_set_status_reason_required_for_reopen(self, setup_db):
        """Reason required for reopening done task."""
        # Full path: draft -> ready -> in_progress -> review -> done
        state_payload = {
            "current_step": "start",
            "constraints": [],
            "done_when": [{"description": "Complete", "done": True}],
            "artifact_refs": [],
            "evidence_refs": [],
            "context_policy": {},
            "confidence": "high",
        }
        main(["--db", setup_db, "state", "put", "--task", "task-001", "--json", json.dumps(state_payload)])
        main(["--db", setup_db, "task", "set-status", "--task", "task-001", "--to", "ready"])
        main(["--db", setup_db, "task", "set-status", "--task", "task-001", "--to", "in_progress"])
        # Add a decision for review
        dec_payload = {"summary": "Done", "confidence": "high"}
        main(["--db", setup_db, "decision", "add", "--task", "task-001", "--json", json.dumps(dec_payload)])
        main(["--db", setup_db, "task", "set-status", "--task", "task-001", "--to", "review"])
        main(["--db", setup_db, "task", "set-status", "--task", "task-001", "--to", "done"])
        # Now try reopen without reason (should require)
        result = main([
            "--db", setup_db, "task", "set-status",
            "--task", "task-001",
            "--to", "in_progress",
            "--reason-required",
        ])
        assert result != 0
"""
Test cases for Task Management.

Corresponds to: docs/tests/task.feature
Spec reference: MVP Spec 5.1, 6.1-6.5, 7.1-7.4
"""

import json

import pytest

from .helpers import (
    agent_taskstate,
    create_task,
    create_task_state,
    create_decision,
    create_open_question,
    cmd_task_create,
    cmd_task_show,
    cmd_task_list,
    cmd_task_update,
    cmd_task_set_status,
)


class TestTaskCreate:
    """Test task create command."""

    def test_create_with_required_fields(self, empty_db):
        """Spec 6.1: Create task with required fields only."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        output = cmd_task_create(
            ctx,
            kind="feature",
            title="新機能",
            goal="実装する",
            priority="high",
            owner_type="agent",
            owner_id="agent-001",
        )

        assert output["ok"] is True
        assert "id" in output["data"]
        assert output["error"] is None

        with agent_taskstate.connect(empty_db) as conn:
            row = conn.execute(
                "SELECT * FROM tasks WHERE id = ?", (output["data"]["id"],)
            ).fetchone()
            assert row is not None
            assert row["status"] == "draft"
            assert row["kind"] == "feature"
            assert row["priority"] == "high"

    def test_create_with_all_fields(self, empty_db):
        """Create task with all fields including parent_task_id."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        with agent_taskstate.connect(empty_db) as conn:
            parent_id = create_task(conn, task_id="01HPARENT001")

        output = cmd_task_create(
            ctx,
            kind="bugfix",
            title="バグ修正",
            goal="修正する",
            priority="critical",
            owner_type="human",
            owner_id="user-001",
            parent_task_id=parent_id,
        )

        assert output["ok"] is True

        with agent_taskstate.connect(empty_db) as conn:
            row = conn.execute(
                "SELECT * FROM tasks WHERE id = ?", (output["data"]["id"],)
            ).fetchone()
            assert row["parent_task_id"] == parent_id

    @pytest.mark.parametrize("kind", ["bugfix", "feature", "research"])
    def test_create_with_each_kind(self, empty_db, kind):
        """Spec 5.1: Create task with each valid kind."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        output = cmd_task_create(
            ctx,
            kind=kind,
            title="Test",
            goal="Goal",
            priority="medium",
            owner_type="agent",
            owner_id="agent-001",
        )

        assert output["ok"] is True
        with agent_taskstate.connect(empty_db) as conn:
            row = conn.execute(
                "SELECT kind FROM tasks WHERE id = ?", (output["data"]["id"],)
            ).fetchone()
            assert row["kind"] == kind

    @pytest.mark.parametrize("priority", ["low", "medium", "high", "critical"])
    def test_create_with_each_priority(self, empty_db, priority):
        """Create task with each valid priority."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        output = cmd_task_create(
            ctx,
            kind="feature",
            title="Test",
            goal="Goal",
            priority=priority,
            owner_type="agent",
            owner_id="agent-001",
        )

        assert output["ok"] is True
        with agent_taskstate.connect(empty_db) as conn:
            row = conn.execute(
                "SELECT priority FROM tasks WHERE id = ?", (output["data"]["id"],)
            ).fetchone()
            assert row["priority"] == priority

    @pytest.mark.parametrize("owner_type,owner_id", [
        ("human", "user-001"),
        ("agent", "agent-001"),
        ("system", "system-001"),
    ])
    def test_create_with_each_owner_type(self, empty_db, owner_type, owner_id):
        """Create task with each valid owner_type."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        output = cmd_task_create(
            ctx,
            kind="feature",
            title="Test",
            goal="Goal",
            priority="medium",
            owner_type=owner_type,
            owner_id=owner_id,
        )

        assert output["ok"] is True
        with agent_taskstate.connect(empty_db) as conn:
            row = conn.execute(
                "SELECT owner_type FROM tasks WHERE id = ?", (output["data"]["id"],)
            ).fetchone()
            assert row["owner_type"] == owner_type


class TestTaskCreateValidation:
    """Test validation errors for task create."""

    def test_create_without_kind_returns_validation_error(self, empty_db):
        """Spec 6.1: kind is required."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        output = cmd_task_create(
            ctx,
            kind=None,
            title="Test",
            goal="Goal",
            priority="high",
            owner_type="agent",
            owner_id="agent-001",
        )

        assert output["ok"] is False
        assert output["error"]["code"] == "validation_error"

    def test_create_with_invalid_kind_returns_validation_error(self, empty_db):
        """Spec 5.1: Invalid kind raises validation_error."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        output = cmd_task_create(
            ctx,
            kind="invalid",
            title="Test",
            goal="Goal",
            priority="high",
            owner_type="agent",
            owner_id="agent-001",
        )

        assert output["ok"] is False
        assert output["error"]["code"] == "validation_error"

    def test_create_with_invalid_priority_returns_validation_error(self, empty_db):
        """Invalid priority raises validation_error."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        output = cmd_task_create(
            ctx,
            kind="feature",
            title="Test",
            goal="Goal",
            priority="urgent",
            owner_type="agent",
            owner_id="agent-001",
        )

        assert output["ok"] is False
        assert output["error"]["code"] == "validation_error"


class TestTaskShow:
    """Test task show command."""

    def test_show_existing_task(self, empty_db):
        """Spec 6.1: Show existing task details."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        with agent_taskstate.connect(empty_db) as conn:
            task_id = create_task(conn, title="Test 1", goal="Goal 1")

        output = cmd_task_show(ctx, task_id=task_id)

        assert output["ok"] is True
        assert output["data"]["id"] == task_id
        assert output["data"]["title"] == "Test 1"
        assert output["data"]["status"] == "draft"

    def test_show_nonexistent_task_returns_not_found(self, empty_db):
        """Spec 10.4: Non-existent task returns not_found."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        output = cmd_task_show(ctx, task_id="01HNOTFOUND001")

        assert output["ok"] is False
        assert output["error"]["code"] == "not_found"


class TestTaskList:
    """Test task list command."""

    def test_list_all_tasks(self, empty_db):
        """Spec 6.1: List all tasks."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        with agent_taskstate.connect(empty_db) as conn:
            create_task(conn, kind="feature", title="Task 1", status="draft")
            create_task(conn, kind="bugfix", title="Task 2", status="in_progress")
            create_task(conn, kind="feature", title="Task 3", status="done")

        output = cmd_task_list(ctx)

        assert output["ok"] is True
        assert len(output["data"]) == 3

    def test_list_filter_by_status(self, empty_db):
        """Spec 6.1: Filter tasks by status."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        with agent_taskstate.connect(empty_db) as conn:
            create_task(conn, title="Task 1", status="draft")
            create_task(conn, title="Task 2", status="in_progress")
            create_task(conn, title="Task 3", status="done")

        output = cmd_task_list(ctx, status="draft")

        assert output["ok"] is True
        assert len(output["data"]) == 1
        assert output["data"][0]["status"] == "draft"

    def test_list_filter_by_kind(self, empty_db):
        """Spec 6.1: Filter tasks by kind."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        with agent_taskstate.connect(empty_db) as conn:
            create_task(conn, kind="feature", title="Task 1")
            create_task(conn, kind="bugfix", title="Task 2")

        output = cmd_task_list(ctx, kind="bugfix")

        assert output["ok"] is True
        assert len(output["data"]) == 1
        assert output["data"][0]["kind"] == "bugfix"

    def test_list_filter_by_owner_type(self, empty_db):
        """Filter tasks by owner_type."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        with agent_taskstate.connect(empty_db) as conn:
            create_task(conn, owner_type="human", owner_id="user-001")
            create_task(conn, owner_type="agent", owner_id="agent-001")

        output = cmd_task_list(ctx, owner_type="agent")

        assert output["ok"] is True
        assert len(output["data"]) == 1
        assert output["data"][0]["owner_type"] == "agent"

    def test_list_no_matching_tasks(self, empty_db):
        """Return empty list when no tasks match filter."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        with agent_taskstate.connect(empty_db) as conn:
            create_task(conn, status="draft")

        output = cmd_task_list(ctx, status="done")

        assert output["ok"] is True
        assert output["data"] == []


class TestTaskUpdate:
    """Test task update command."""

    def test_update_title(self, empty_db):
        """Update task title."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        with agent_taskstate.connect(empty_db) as conn:
            task_id = create_task(conn, title="Before")

        output = cmd_task_update(ctx, task_id=task_id, title="After")

        assert output["ok"] is True
        with agent_taskstate.connect(empty_db) as conn:
            row = conn.execute(
                "SELECT title FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
            assert row["title"] == "After"

    def test_update_nonexistent_task_returns_not_found(self, empty_db):
        """Update non-existent task returns not_found."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        output = cmd_task_update(ctx, task_id="01HNOTFOUND001", title="New Title")

        assert output["ok"] is False
        assert output["error"]["code"] == "not_found"


class TestTaskSetStatus:
    """Test task set-status command."""

    def test_draft_to_ready_transition(self, empty_db):
        """Spec 7.2: draft -> ready transition."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        with agent_taskstate.connect(empty_db) as conn:
            task_id = create_task(conn, status="draft", goal="Goal 1", kind="feature")
            create_task_state(conn, task_id, done_when=["条件1", "条件2"])

        output = cmd_task_set_status(ctx, task_id=task_id, to_status="ready")

        assert output["ok"] is True
        with agent_taskstate.connect(empty_db) as conn:
            row = conn.execute(
                "SELECT status FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
            assert row["status"] == "ready"

    def test_ready_to_in_progress_transition(self, empty_db):
        """Spec 7.2: ready -> in_progress transition."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        with agent_taskstate.connect(empty_db) as conn:
            task_id = create_task(conn, status="ready")
            create_task_state(conn, task_id, current_step="実装中")

        output = cmd_task_set_status(ctx, task_id=task_id, to_status="in_progress", reason="Starting work")

        assert output["ok"] is True

    def test_in_progress_to_blocked_transition(self, empty_db):
        """Spec 7.2: in_progress -> blocked transition."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        with agent_taskstate.connect(empty_db) as conn:
            task_id = create_task(conn, status="in_progress")

        output = cmd_task_set_status(ctx, task_id=task_id, to_status="blocked")

        assert output["ok"] is True

    def test_in_progress_to_review_transition(self, empty_db):
        """Spec 7.2: in_progress -> review transition."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        with agent_taskstate.connect(empty_db) as conn:
            task_id = create_task(conn, status="in_progress")
            create_decision(conn, task_id, status="accepted")

        output = cmd_task_set_status(ctx, task_id=task_id, to_status="review")

        assert output["ok"] is True

    def test_done_to_archived_transition(self, empty_db):
        """Spec 7.2: done -> archived transition."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        with agent_taskstate.connect(empty_db) as conn:
            task_id = create_task(conn, status="done")

        output = cmd_task_set_status(ctx, task_id=task_id, to_status="archived", reason="Completed")

        assert output["ok"] is True


class TestTaskSetStatusGuardViolations:
    """Test guard condition violations for status transitions."""

    def test_ready_transition_goal_empty(self, empty_db):
        """Spec 7.4: Cannot transition to ready when goal is empty."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        with agent_taskstate.connect(empty_db) as conn:
            task_id = create_task(conn, status="draft", goal="", kind="feature")
            create_task_state(conn, task_id, done_when=["条件1"])

        output = cmd_task_set_status(ctx, task_id=task_id, to_status="ready")

        assert output["ok"] is False
        assert output["error"]["code"] in ("invalid_transition", "dependency_blocked", "validation_error")

    def test_review_transition_high_priority_open_question(self, empty_db):
        """Spec 7.4: Cannot transition to review with high priority open question."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        with agent_taskstate.connect(empty_db) as conn:
            task_id = create_task(conn, status="in_progress")
            create_decision(conn, task_id, status="accepted")
            create_open_question(conn, task_id, priority="high", status="open")

        output = cmd_task_set_status(ctx, task_id=task_id, to_status="review")

        assert output["ok"] is False
        assert output["error"]["code"] in ("invalid_transition", "dependency_blocked", "validation_error")


class TestTaskSetStatusDisallowed:
    """Test disallowed status transitions."""

    def test_draft_to_in_progress_disallowed(self, empty_db):
        """Spec 7.2: draft -> in_progress is not allowed."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        with agent_taskstate.connect(empty_db) as conn:
            task_id = create_task(conn, status="draft")

        output = cmd_task_set_status(ctx, task_id=task_id, to_status="in_progress")

        assert output["ok"] is False
        assert output["error"]["code"] in ("invalid_transition", "dependency_blocked", "validation_error")

    def test_draft_to_done_disallowed(self, empty_db):
        """Spec 7.2: draft -> done is not allowed."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        with agent_taskstate.connect(empty_db) as conn:
            task_id = create_task(conn, status="draft")

        output = cmd_task_set_status(ctx, task_id=task_id, to_status="done")

        assert output["ok"] is False
        assert output["error"]["code"] in ("invalid_transition", "dependency_blocked", "validation_error")
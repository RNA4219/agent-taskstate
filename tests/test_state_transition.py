"""
Tests for state_transition module.

Covers:
- State transition validation
- History tracking
- Terminal state handling
"""

import pytest
import sqlite3

from src.state_transition import (
    StateTransitionService,
    InvalidTransitionError,
    TerminalStateError,
    MissingReasonError,
    can_transition,
    is_terminal,
    requires_reason,
    create_transition_table,
    ALLOWED_TRANSITIONS,
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

    # Create transition table
    create_transition_table(conn)

    yield conn
    conn.close()


@pytest.fixture
def service(conn):
    """Create a StateTransitionService instance."""
    return StateTransitionService(conn)


@pytest.fixture
def task(conn):
    """Create a test task."""
    conn.execute(
        "INSERT INTO task (id, status, updated_at) VALUES (?, ?, ?)",
        ("task_001", "proposed", "2024-01-01T00:00:00.000000Z"),
    )
    return "task_001"


class TestCanTransition:
    """Test can_transition function."""

    def test_proposed_to_ready(self):
        """proposed -> ready is allowed."""
        assert can_transition("proposed", "ready") is True

    def test_proposed_to_cancelled(self):
        """proposed -> cancelled is allowed."""
        assert can_transition("proposed", "cancelled") is True

    def test_ready_to_in_progress(self):
        """ready -> in_progress is allowed."""
        assert can_transition("ready", "in_progress") is True

    def test_in_progress_to_blocked(self):
        """in_progress -> blocked is allowed."""
        assert can_transition("in_progress", "blocked") is True

    def test_in_progress_to_review(self):
        """in_progress -> review is allowed."""
        assert can_transition("in_progress", "review") is True

    def test_review_to_done(self):
        """review -> done is allowed."""
        assert can_transition("review", "done") is True

    def test_done_to_in_progress(self):
        """done -> in_progress (reopen) is allowed."""
        assert can_transition("done", "in_progress") is True

    def test_done_to_ready_not_allowed(self):
        """done -> ready is not allowed."""
        assert can_transition("done", "ready") is False

    def test_cancelled_cannot_transition(self):
        """cancelled cannot transition to anything."""
        assert can_transition("cancelled", "proposed") is False
        assert can_transition("cancelled", "ready") is False


class TestIsTerminal:
    """Test is_terminal function."""

    def test_done_is_terminal(self):
        """done is a terminal state."""
        assert is_terminal("done") is True

    def test_cancelled_is_terminal(self):
        """cancelled is a terminal state."""
        assert is_terminal("cancelled") is True

    def test_proposed_not_terminal(self):
        """proposed is not a terminal state."""
        assert is_terminal("proposed") is False

    def test_in_progress_not_terminal(self):
        """in_progress is not a terminal state."""
        assert is_terminal("in_progress") is False


class TestRequiresReason:
    """Test requires_reason function."""

    def test_done_to_in_progress_requires_reason(self):
        """Reopen (done -> in_progress) requires reason."""
        assert requires_reason("done", "in_progress") is True

    def test_review_to_done_requires_reason(self):
        """review -> done requires reason."""
        assert requires_reason("review", "done") is True

    def test_proposed_to_ready_no_reason_required(self):
        """proposed -> ready does not require reason."""
        assert requires_reason("proposed", "ready") is False

    def test_any_to_cancelled_requires_reason(self):
        """Transition to cancelled requires reason."""
        assert requires_reason("proposed", "cancelled") is True
        assert requires_reason("in_progress", "cancelled") is True


class TestStateTransitionService:
    """Test StateTransitionService."""

    def test_transition_creates_record(self, service, task, conn):
        """Transition creates a history record."""
        transition = service.transition(
            task_id=task,
            to_status="ready",
            reason="Task is ready to start",
            actor_type="human",
            actor_id="user_001",
        )

        assert transition.task_id == task
        assert transition.from_status == "proposed"
        assert transition.to_status == "ready"
        assert transition.reason == "Task is ready to start"
        assert transition.actor_type == "human"

        # Check task status was updated
        cursor = conn.execute("SELECT status FROM task WHERE id = ?", (task,))
        assert cursor.fetchone()[0] == "ready"

    def test_transition_history(self, service, task):
        """Multiple transitions create history."""
        service.transition(task, "ready", "Ready", "human", "user_001")
        service.transition(task, "in_progress", "Started", "agent", "agent_001")
        service.transition(task, "review", "For review", "agent", "agent_001")

        history = service.get_history(task)
        assert len(history) == 3

        # Check that all transitions are present
        # Order may vary due to timestamp precision
        to_statuses = [h.to_status for h in history]
        assert "ready" in to_statuses
        assert "in_progress" in to_statuses
        assert "review" in to_statuses

    def test_invalid_transition_raises(self, service, task):
        """Invalid transition raises error."""
        # Try to go directly from proposed to in_progress
        with pytest.raises(InvalidTransitionError):
            service.transition(
                task_id=task,
                to_status="in_progress",
                reason="Skip ready",
                actor_type="human",
            )

    def test_terminal_state_raises(self, service, task, conn):
        """Transition from terminal state raises error."""
        # Move to done
        service.transition(task, "ready", "Ready", "human")
        service.transition(task, "in_progress", "Started", "agent")
        service.transition(task, "review", "Review", "agent")
        service.transition(task, "done", "Completed", "human")

        # Try to move to ready (not allowed)
        with pytest.raises((TerminalStateError, InvalidTransitionError)):
            service.transition(task, "ready", "Reopen wrong way", "human")

    def test_reopen_requires_reason(self, service, task):
        """Reopen (done -> in_progress) requires reason."""
        # Move to done
        service.transition(task, "ready", "Ready", "human")
        service.transition(task, "in_progress", "Started", "agent")
        service.transition(task, "review", "Review", "agent")
        service.transition(task, "done", "Completed", "human")

        # Try reopen without reason
        with pytest.raises(MissingReasonError):
            service.transition(
                task_id=task,
                to_status="in_progress",
                reason="",  # Empty reason
                actor_type="human",
            )

    def test_reopen_with_reason(self, service, task):
        """Reopen with reason succeeds."""
        # Move to done
        service.transition(task, "ready", "Ready", "human")
        service.transition(task, "in_progress", "Started", "agent")
        service.transition(task, "review", "Review", "agent")
        service.transition(task, "done", "Completed", "human")

        # Reopen with reason
        transition = service.transition(
            task_id=task,
            to_status="in_progress",
            reason="Reopen: additional work needed",
            actor_type="human",
        )

        assert transition.from_status == "done"
        assert transition.to_status == "in_progress"

    def test_get_current_state(self, service, task):
        """Get current state returns task status."""
        assert service.get_current_state(task) == "proposed"

        service.transition(task, "ready", "Ready", "human")
        assert service.get_current_state(task) == "ready"

    def test_transition_with_run_id(self, service, task):
        """Transition can be associated with a run."""
        transition = service.transition(
            task_id=task,
            to_status="ready",
            reason="Auto-activated by run",
            actor_type="system",
            run_id="run_001",
        )

        assert transition.run_id == "run_001"


class TestAllowedTransitions:
    """Test ALLOWED_TRANSITIONS constant."""

    def test_proposed_transitions(self):
        """proposed can transition to ready or cancelled."""
        assert ALLOWED_TRANSITIONS["proposed"] == {"ready", "cancelled"}

    def test_done_transitions(self):
        """done can only transition to in_progress (reopen)."""
        assert ALLOWED_TRANSITIONS["done"] == {"in_progress"}

    def test_cancelled_no_transitions(self):
        """cancelled has no outgoing transitions."""
        assert ALLOWED_TRANSITIONS["cancelled"] == set()
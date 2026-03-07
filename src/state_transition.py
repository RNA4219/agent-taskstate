"""
State Transition Service

Manages task state transitions with history tracking.
All status changes must go through this service.

Design principles:
- task.status is materialized current state
- state_transition table holds append-only history
- Every transition has reason and actor
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

# Allowed transitions based on state-machine.md
ALLOWED_TRANSITIONS = {
    "proposed": {"ready", "cancelled"},
    "ready": {"in_progress", "cancelled"},
    "in_progress": {"blocked", "review", "cancelled"},
    "blocked": {"in_progress", "cancelled"},
    "review": {"in_progress", "done", "cancelled"},
    "done": {"in_progress"},  # reopen (exception, requires reason)
    "cancelled": set(),
}

TERMINAL_STATES = {"done", "cancelled"}

ACTOR_TYPES = {"human", "agent", "system"}


@dataclass
class StateTransition:
    """Represents a single state transition record."""

    id: str
    task_id: str
    from_status: Optional[str]
    to_status: str
    reason: str
    actor_type: str
    actor_id: Optional[str]
    run_id: Optional[str]
    changed_at: str


class InvalidTransitionError(Exception):
    """Raised when attempting an invalid state transition."""

    def __init__(self, from_status: str, to_status: str):
        self.from_status = from_status
        self.to_status = to_status
        super().__init__(
            f"Invalid transition: {from_status} -> {to_status}"
        )


class TerminalStateError(Exception):
    """Raised when attempting to transition from a terminal state."""

    def __init__(self, status: str):
        self.status = status
        super().__init__(
            f"Cannot transition from terminal state: {status}"
        )


class MissingReasonError(Exception):
    """Raised when a required reason is not provided."""

    def __init__(self, transition: str):
        self.transition = transition
        super().__init__(
            f"Reason required for transition: {transition}"
        )


def now_utc() -> str:
    """Return current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def gen_id() -> str:
    """Generate a unique ID."""
    import uuid
    return uuid.uuid4().hex


def can_transition(from_status: str, to_status: str) -> bool:
    """
    Check if a transition is allowed.

    Args:
        from_status: Current status
        to_status: Target status

    Returns:
        True if transition is allowed, False otherwise
    """
    if from_status not in ALLOWED_TRANSITIONS:
        return False
    return to_status in ALLOWED_TRANSITIONS[from_status]


def is_terminal(status: str) -> bool:
    """Check if a status is terminal (no outgoing transitions)."""
    return status in TERMINAL_STATES


def requires_reason(from_status: str, to_status: str) -> bool:
    """
    Check if a transition requires a reason.

    Exception transitions (reopen, etc.) require reason.
    """
    # done -> in_progress (reopen) requires reason
    if from_status == "done" and to_status == "in_progress":
        return True
    # Terminal state transitions require reason
    if to_status in TERMINAL_STATES:
        return True
    return False


class StateTransitionService:
    """
    Service for managing task state transitions.

    All task status changes must go through this service to ensure
    history is properly recorded.
    """

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def transition(
        self,
        task_id: str,
        to_status: str,
        reason: str,
        actor_type: str,
        actor_id: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> StateTransition:
        """
        Execute a state transition.

        Args:
            task_id: Task ID
            to_status: Target status
            reason: Reason for transition
            actor_type: Type of actor (human/agent/system)
            actor_id: Optional actor identifier
            run_id: Optional run ID for correlation

        Returns:
            StateTransition record

        Raises:
            InvalidTransitionError: If transition is not allowed
            TerminalStateError: If trying to transition from terminal state
            MissingReasonError: If required reason is not provided
        """
        # Validate actor type
        if actor_type not in ACTOR_TYPES:
            raise ValueError(f"Invalid actor_type: {actor_type}")

        # Get current task status
        cursor = self.conn.execute(
            "SELECT status FROM task WHERE id = ?", (task_id,)
        )
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Task not found: {task_id}")

        from_status = row[0]

        # Check if transition is allowed
        if not can_transition(from_status, to_status):
            if is_terminal(from_status):
                raise TerminalStateError(from_status)
            raise InvalidTransitionError(from_status, to_status)

        # Check if reason is required
        if requires_reason(from_status, to_status) and not reason:
            raise MissingReasonError(f"{from_status} -> {to_status}")

        # Create transition record
        transition_id = gen_id()
        changed_at = now_utc()

        self.conn.execute(
            """
            INSERT INTO task_state
                (id, task_id, from_state, to_state, reason, actor_type, actor_id, run_id, changed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                transition_id,
                task_id,
                from_status,
                to_status,
                reason,
                actor_type,
                actor_id,
                run_id,
                changed_at,
            ),
        )

        # Update task status (materialized current state)
        self.conn.execute(
            "UPDATE task SET status = ?, updated_at = ? WHERE id = ?",
            (to_status, changed_at, task_id),
        )

        return StateTransition(
            id=transition_id,
            task_id=task_id,
            from_status=from_status,
            to_status=to_status,
            reason=reason,
            actor_type=actor_type,
            actor_id=actor_id,
            run_id=run_id,
            changed_at=changed_at,
        )

    def get_history(self, task_id: str) -> List[StateTransition]:
        """
        Get state transition history for a task.

        Args:
            task_id: Task ID

        Returns:
            List of StateTransition records, oldest first
        """
        cursor = self.conn.execute(
            """
            SELECT id, task_id, from_state, to_state, reason, actor_type, actor_id, run_id, changed_at
            FROM task_state
            WHERE task_id = ?
            ORDER BY changed_at ASC
            """,
            (task_id,),
        )

        transitions = []
        for row in cursor.fetchall():
            transitions.append(
                StateTransition(
                    id=row[0],
                    task_id=row[1],
                    from_status=row[2],
                    to_status=row[3],
                    reason=row[4],
                    actor_type=row[5],
                    actor_id=row[6],
                    run_id=row[7],
                    changed_at=row[8],
                )
            )

        return transitions

    def get_current_state(self, task_id: str) -> Optional[str]:
        """
        Get current status of a task.

        Args:
            task_id: Task ID

        Returns:
            Current status or None if task not found
        """
        cursor = self.conn.execute(
            "SELECT status FROM task WHERE id = ?", (task_id,)
        )
        row = cursor.fetchone()
        return row[0] if row else None


def create_transition_table(conn: sqlite3.Connection) -> None:
    """Create the task_state table if it doesn't exist."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS task_state (
            id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
            from_state TEXT,
            to_state TEXT NOT NULL,
            reason TEXT NOT NULL,
            actor_type TEXT NOT NULL,
            actor_id TEXT,
            run_id TEXT,
            changed_at TEXT NOT NULL,
            FOREIGN KEY (task_id) REFERENCES task(id)
        )
        """
    )

    # Create index for efficient history queries
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_task_state_task_changed
        ON task_state(task_id, changed_at DESC)
        """
    )
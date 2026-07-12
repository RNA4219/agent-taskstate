"""Append-only task status transitions.

The service prefers the 1.1.0 plural tables and retains a small compatibility
path for callers that still construct the old singular test schema.
"""

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

from .transition_config import DEFAULT_CONFIG, TransitionConfig

ALLOWED_TRANSITIONS = DEFAULT_CONFIG.allowed_transitions
TERMINAL_STATES = DEFAULT_CONFIG.terminal_states
ACTOR_TYPES = DEFAULT_CONFIG.actor_types


@dataclass
class StateTransition:
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
    def __init__(self, from_status: str, to_status: str):
        self.from_status = from_status
        self.to_status = to_status
        super().__init__(f"Invalid transition: {from_status} -> {to_status}")


class TerminalStateError(Exception):
    def __init__(self, status: str):
        self.status = status
        super().__init__(f"Cannot transition from terminal state: {status}")


class MissingReasonError(Exception):
    def __init__(self, transition: str):
        self.transition = transition
        super().__init__(f"Reason required for transition: {transition}")


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def gen_id() -> str:
    return uuid.uuid4().hex


def can_transition(from_status: str, to_status: str) -> bool:
    return to_status in ALLOWED_TRANSITIONS.get(from_status, set())


def is_terminal(status: str) -> bool:
    return status in TERMINAL_STATES


def requires_reason(from_status: str, to_status: str) -> bool:
    if from_status == "done" and to_status == "in_progress":
        return True
    if to_status in TERMINAL_STATES:
        return True
    return False


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
        ).fetchone()
        is not None
    )


class StateTransitionService:
    """Perform status updates and history inserts in the caller's transaction."""

    def __init__(self, conn: sqlite3.Connection, config: Optional[TransitionConfig] = None):
        self.conn = conn
        self.config = config or DEFAULT_CONFIG

    @property
    def allowed_transitions(self) -> dict:
        return self.config.allowed_transitions

    @property
    def terminal_states(self) -> set:
        return self.config.terminal_states

    @property
    def actor_types(self) -> set:
        return self.config.actor_types

    def can_transition(self, from_status: str, to_status: str) -> bool:
        return self.config.can_transition(from_status, to_status)

    def is_terminal(self, status: str) -> bool:
        return self.config.is_terminal(status)

    def requires_reason(self, from_status: str, to_status: str) -> bool:
        return self.config.requires_reason(from_status, to_status)

    def _plural(self) -> bool:
        return _table_exists(self.conn, "tasks")

    def transition(
        self,
        task_id: str,
        to_status: str,
        reason: str = "",
        actor_type: str = "system",
        actor_id: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> Optional[StateTransition]:
        if not self.config.is_valid_actor(actor_type):
            raise ValueError(f"Invalid actor_type: {actor_type}")

        plural = self._plural()
        task_table = "tasks" if plural else "task"
        history_table = "state_transitions" if plural else "task_state"
        from_column = "from_status" if plural else "from_state"
        to_column = "to_status" if plural else "to_state"
        row = self.conn.execute(
            f"SELECT status FROM {task_table} WHERE id = ?", (task_id,)
        ).fetchone()
        if not row:
            raise ValueError(f"Task not found: {task_id}")
        from_status = row[0]

        # A repeated status is an intentional successful no-op.
        if from_status == to_status:
            return None
        if not self.can_transition(from_status, to_status):
            if self.is_terminal(from_status):
                raise TerminalStateError(from_status)
            raise InvalidTransitionError(from_status, to_status)
        if self.requires_reason(from_status, to_status) and not reason:
            raise MissingReasonError(f"{from_status} -> {to_status}")

        transition_id = gen_id()
        changed_at = now_utc()
        self.conn.execute(
            f"""
            INSERT INTO {history_table}
              (id, task_id, {from_column}, {to_column}, reason, actor_type, actor_id, run_id, changed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                transition_id,
                task_id,
                from_status,
                to_status,
                reason or "",
                actor_type,
                actor_id,
                run_id,
                changed_at,
            ),
        )
        self.conn.execute(
            f"UPDATE {task_table} SET status = ?, updated_at = ? WHERE id = ?",
            (to_status, changed_at, task_id),
        )
        return StateTransition(
            id=transition_id,
            task_id=task_id,
            from_status=from_status,
            to_status=to_status,
            reason=reason or "",
            actor_type=actor_type,
            actor_id=actor_id,
            run_id=run_id,
            changed_at=changed_at,
        )

    def record_initial(
        self, task_id: str, status: str, changed_at: Optional[str] = None
    ) -> StateTransition:
        """Record the task-create transition with a NULL source status."""
        if not self._plural():
            raise ValueError("record_initial requires the plural schema")
        exists = self.conn.execute(
            "SELECT id FROM state_transitions WHERE task_id = ? AND from_status IS NULL",
            (task_id,),
        ).fetchone()
        if exists:
            return self.get_history(task_id)[0]
        transition = StateTransition(
            id=gen_id(),
            task_id=task_id,
            from_status=None,
            to_status=status,
            reason="task_created",
            actor_type="system",
            actor_id=None,
            run_id=None,
            changed_at=changed_at or now_utc(),
        )
        self.conn.execute(
            """
            INSERT INTO state_transitions
              (id, task_id, from_status, to_status, reason, actor_type, changed_at)
            VALUES (?, ?, NULL, ?, ?, 'system', ?)
            """,
            (transition.id, task_id, status, transition.reason, transition.changed_at),
        )
        return transition

    def get_history(self, task_id: str) -> List[StateTransition]:
        plural = self._plural()
        table = "state_transitions" if plural else "task_state"
        from_column = "from_status" if plural else "from_state"
        to_column = "to_status" if plural else "to_state"
        rows = self.conn.execute(
            f"""
            SELECT id, task_id, {from_column}, {to_column}, reason, actor_type, actor_id, run_id, changed_at
            FROM {table} WHERE task_id = ? ORDER BY changed_at ASC, id ASC
            """,
            (task_id,),
        ).fetchall()
        return [
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
            for row in rows
        ]

    def get_current_state(self, task_id: str) -> Optional[str]:
        table = "tasks" if self._plural() else "task"
        row = self.conn.execute(f"SELECT status FROM {table} WHERE id = ?", (task_id,)).fetchone()
        return row[0] if row else None


def create_transition_table(conn: sqlite3.Connection) -> None:
    """Create the canonical history table, or the legacy test table if needed."""
    if _table_exists(conn, "tasks"):
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS state_transitions (
              id TEXT PRIMARY KEY, task_id TEXT NOT NULL, from_status TEXT,
              to_status TEXT NOT NULL, reason TEXT NOT NULL DEFAULT '',
              actor_type TEXT NOT NULL, actor_id TEXT, run_id TEXT, changed_at TEXT NOT NULL,
              FOREIGN KEY(task_id) REFERENCES tasks(id)
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_state_transitions_task_changed "
            "ON state_transitions(task_id, changed_at ASC, id ASC)"
        )
    else:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS task_state (
              id TEXT PRIMARY KEY, task_id TEXT NOT NULL, from_state TEXT,
              to_state TEXT NOT NULL, reason TEXT NOT NULL, actor_type TEXT NOT NULL,
              actor_id TEXT, run_id TEXT, changed_at TEXT NOT NULL,
              FOREIGN KEY(task_id) REFERENCES task(id)
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_task_state_task_changed "
            "ON task_state(task_id, changed_at DESC)"
        )

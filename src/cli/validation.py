"""
CLI Validation and Guards
"""

from __future__ import annotations

import sqlite3
from typing import Any, Dict, List, Optional, Sequence

from .constants import (
    ALLOWED_TRANSITIONS,
    CONFIDENCE_LEVELS,
    DECISION_STATUSES,
    OWNER_TYPES,
    QUESTION_PRIORITIES,
    QUESTION_STATUSES,
    REPLY_STATES,
    RUN_STATUSES,
    RUN_TYPES,
    TASK_KINDS,
    TASK_PRIORITIES,
    TASK_STATUSES,
)
from .errors import AgentTaskstateError, DependencyBlockedError, InvalidTransitionError
from .fetch import get_task_state
from .models import jdump, row_to_task_state


def require_in(value: str, allowed: Sequence[str] | set[str], field: str) -> None:
    """Require value to be in allowed set."""
    if value not in allowed:
        raise AgentTaskstateError(f"invalid {field}: {value}; allowed={sorted(allowed)}")


def load_json_arg(value: Optional[str] = None, file_path: Optional[str] = None) -> Any:
    """Load JSON from argument or file."""
    import json
    from pathlib import Path

    if value and file_path:
        raise AgentTaskstateError("pass either --json or --file, not both")
    if file_path:
        return json.loads(Path(file_path).read_text(encoding="utf-8"))
    if value:
        return json.loads(value)
    raise AgentTaskstateError("missing JSON payload; pass --json or --file")


def _normalize_optional_json_text(value: Any) -> Optional[str]:
    """Normalize optional JSON to text."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return jdump(value)


def validate_task_payload(data: Dict[str, Any]) -> None:
    """Validate task payload."""
    require_in(data["kind"], TASK_KINDS, "kind")
    require_in(data.get("status", "draft"), TASK_STATUSES, "status")
    require_in(data.get("priority", "medium"), TASK_PRIORITIES, "priority")
    require_in(data.get("owner_type", "human"), OWNER_TYPES, "owner_type")
    if data.get("parent_task_id") and not isinstance(data["parent_task_id"], str):
        raise AgentTaskstateError("parent_task_id must be string")
    if data.get("reply_state") is not None:
        require_in(data["reply_state"], REPLY_STATES, "reply_state")
    if data.get("retry_count") is not None:
        if not isinstance(data["retry_count"], int) or data["retry_count"] < 0:
            raise AgentTaskstateError("retry_count must be non-negative integer")


def validate_state_payload(data: Dict[str, Any]) -> None:
    """Validate task_state payload."""
    if not data.get("current_step"):
        raise AgentTaskstateError("current_step is required")
    if not isinstance(data.get("constraints", []), list):
        raise AgentTaskstateError("constraints must be array")
    if not isinstance(data.get("done_when", []), list):
        raise AgentTaskstateError("done_when must be array")
    if not isinstance(data.get("artifact_refs", []), list):
        raise AgentTaskstateError("artifact_refs must be array")
    if not isinstance(data.get("evidence_refs", []), list):
        raise AgentTaskstateError("evidence_refs must be array")
    if not isinstance(data.get("context_policy", {}), dict):
        raise AgentTaskstateError("context_policy must be object")
    require_in(data.get("confidence"), CONFIDENCE_LEVELS, "confidence")


def validate_decision_payload(data: Dict[str, Any]) -> None:
    """Validate decision payload."""
    if not data.get("summary"):
        raise AgentTaskstateError("summary is required")
    require_in(data.get("status", "proposed"), DECISION_STATUSES, "decision.status")
    require_in(data.get("confidence", "medium"), CONFIDENCE_LEVELS, "decision.confidence")
    if not isinstance(data.get("evidence_refs", []), list):
        raise AgentTaskstateError("evidence_refs must be array")


def validate_question_payload(data: Dict[str, Any]) -> None:
    """Validate question payload."""
    if not data.get("question"):
        raise AgentTaskstateError("question is required")
    require_in(data.get("priority", "medium"), QUESTION_PRIORITIES, "question.priority")
    require_in(data.get("status", "open"), QUESTION_STATUSES, "question.status")
    if not isinstance(data.get("evidence_refs", []), list):
        raise AgentTaskstateError("evidence_refs must be array")


def count_open_high_questions(conn: sqlite3.Connection, task_id: str) -> int:
    """Count open high-priority questions."""
    row = conn.execute(
        "SELECT COUNT(*) AS c FROM open_questions WHERE task_id = ? AND status = 'open' AND priority = 'high'",
        (task_id,),
    ).fetchone()
    return int(row["c"])


def count_relevant_decisions(conn: sqlite3.Connection, task_id: str) -> int:
    """Count accepted/proposed decisions."""
    row = conn.execute(
        "SELECT COUNT(*) AS c FROM decisions WHERE task_id = ? AND status IN ('accepted', 'proposed')",
        (task_id,),
    ).fetchone()
    return int(row["c"])


def is_done_when_satisfied(done_when: List[Any]) -> bool:
    """Check if all done_when items are satisfied."""
    if not done_when:
        return False
    for item in done_when:
        if isinstance(item, dict):
            if not bool(item.get("done", False)):
                return False
        else:
            return False
    return True


def validate_status_transition(
    conn: sqlite3.Connection, task_row: sqlite3.Row, to_status: str
) -> None:
    """Validate status transition with guards."""
    require_in(to_status, TASK_STATUSES, "status")
    from_status = task_row["status"]
    if to_status not in ALLOWED_TRANSITIONS.get(from_status, set()):
        raise InvalidTransitionError(f"transition not allowed: {from_status} -> {to_status}")

    task = dict(task_row)
    state: Optional[Dict[str, Any]] = None
    try:
        state = row_to_task_state(get_task_state(conn, task_row["id"]))
    except Exception:
        state = None

    if to_status == "ready":
        if not task["goal"]:
            raise DependencyBlockedError("goal must be set before moving to ready")
        if not state or not state["done_when"]:
            raise DependencyBlockedError("done_when must contain at least one item before moving to ready")
        if not task["kind"]:
            raise DependencyBlockedError("kind must be set before moving to ready")

    if to_status == "in_progress":
        if not state:
            raise DependencyBlockedError("task_state must exist before moving to in_progress")
        if not state["current_step"]:
            raise DependencyBlockedError("current_step must be set before moving to in_progress")

    if to_status == "review":
        if count_open_high_questions(conn, task_row["id"]) > 0:
            raise DependencyBlockedError("high priority open questions must be 0 before moving to review")
        if count_relevant_decisions(conn, task_row["id"]) == 0:
            raise DependencyBlockedError("at least one accepted/proposed decision is required before moving to review")

    if to_status == "done":
        if from_status != "review":
            raise InvalidTransitionError("done is only allowed from review")
        if not state:
            raise DependencyBlockedError("task_state must exist before moving to done")
        if not is_done_when_satisfied(state["done_when"]):
            raise DependencyBlockedError("all done_when items must be satisfied before moving to done")
        if not state.get("current_summary"):
            raise DependencyBlockedError("current_summary must be set before moving to done")
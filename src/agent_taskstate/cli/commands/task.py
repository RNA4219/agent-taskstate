"""Canonical task commands."""

from __future__ import annotations

import argparse
from typing import Any, Dict, List

from ...state_transition import (
    InvalidTransitionError as ServiceInvalidTransitionError,
    MissingReasonError,
    StateTransitionService,
    TerminalStateError,
)
from .. import AppContext
from ..constants import TASK_KINDS, TASK_PRIORITIES, TASK_STATUSES, OWNER_TYPES, REPLY_STATES
from ..db import connect, init_db
from ..errors import AgentTaskstateError
from ..fetch import get_task, get_task_state
from ..models import row_to_task, row_to_task_state
from ..typed_ref import task_ref
from ..utils import gen_id, now_utc, json_ok
from ..validation import (
    _normalize_optional_json_text,
    canonicalize_optional_ref,
    load_json_arg,
    require_in,
    validate_status_transition,
    validate_task_payload,
)


def _transition_error(exc: Exception) -> AgentTaskstateError:
    if isinstance(exc, MissingReasonError):
        return AgentTaskstateError(str(exc), code="validation_error")
    if isinstance(exc, (ServiceInvalidTransitionError, TerminalStateError)):
        return AgentTaskstateError(str(exc), code="invalid_transition")
    if isinstance(exc, ValueError) and "Task not found" in str(exc):
        return AgentTaskstateError(str(exc), code="not_found")
    return AgentTaskstateError(str(exc))


def cmd_init(ctx: AppContext, _args: argparse.Namespace) -> int:
    with connect(ctx.db_path) as conn:
        init_db(conn)
    return json_ok({"db_path": ctx.db_path, "initialized": True})


def cmd_task_create(ctx: AppContext, args: argparse.Namespace) -> int:
    payload = load_json_arg(args.json, args.file)
    validate_task_payload(payload)
    task_id = payload.get("id") or gen_id()
    now = now_utc()
    roadmap_request_json = _normalize_optional_json_text(payload.get("roadmap_request_json"))
    tracker_issue_ref = canonicalize_optional_ref(
        payload.get("tracker_issue_ref"), "tracker_issue_ref"
    )
    with connect(ctx.db_path) as conn:
        init_db(conn)
        if payload.get("parent_task_id"):
            get_task(conn, payload["parent_task_id"])
        conn.execute(
            """
            INSERT INTO tasks (
              id, parent_task_id, kind, title, goal, status, priority, owner_type, owner_id,
              tracker_issue_ref, idempotency_key, note_id, trace_id, reply_target, reply_state,
              retry_count, kestra_execution_id, original_task_id, trigger, reply_text,
              roadmap_request_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task_id,
                payload.get("parent_task_id"),
                payload["kind"],
                payload["title"],
                payload["goal"],
                payload.get("status", "draft"),
                payload.get("priority", "medium"),
                payload.get("owner_type", "human"),
                payload.get("owner_id"),
                tracker_issue_ref,
                payload.get("idempotency_key"),
                payload.get("note_id"),
                payload.get("trace_id"),
                payload.get("reply_target"),
                payload.get("reply_state"),
                payload.get("retry_count", 0),
                payload.get("kestra_execution_id"),
                payload.get("original_task_id"),
                payload.get("trigger"),
                payload.get("reply_text"),
                roadmap_request_json,
                now,
                now,
            ),
        )
        StateTransitionService(conn).record_initial(task_id, payload.get("status", "draft"), now)
        row = get_task(conn, task_id)
    return json_ok({**row_to_task(row), "ref": task_ref(task_id)})


def cmd_task_show(ctx: AppContext, args: argparse.Namespace) -> int:
    with connect(ctx.db_path) as conn:
        row = get_task(conn, args.task)
        data = row_to_task(row)
        data["ref"] = task_ref(args.task)
        try:
            data["state"] = row_to_task_state(get_task_state(conn, args.task))
        except Exception:
            data["state"] = None
    return json_ok(data)


def cmd_task_list(ctx: AppContext, args: argparse.Namespace) -> int:
    clauses: List[str] = []
    params: List[Any] = []
    for name, column in (
        ("status", "status"),
        ("kind", "kind"),
        ("owner_type", "owner_type"),
        ("owner_id", "owner_id"),
        ("priority", "priority"),
        ("reply_state", "reply_state"),
        ("trace_id", "trace_id"),
    ):
        value = getattr(args, name, None)
        if value:
            clauses.append(f"{column} = ?")
            params.append(value)
    if getattr(args, "updated_before", None):
        clauses.append("updated_at < ?")
        params.append(args.updated_before)
    if getattr(args, "idempotency_key", None):
        clauses.append("idempotency_key = ?")
        params.append(args.idempotency_key)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"SELECT * FROM tasks {where} ORDER BY updated_at DESC, created_at DESC"
    with connect(ctx.db_path) as conn:
        init_db(conn)
        rows = conn.execute(sql, params).fetchall()
    return json_ok([{**row_to_task(row), "ref": task_ref(row["id"])} for row in rows])


def cmd_task_update(ctx: AppContext, args: argparse.Namespace) -> int:
    payload = load_json_arg(args.json, args.file)
    allowed = {
        "parent_task_id",
        "kind",
        "title",
        "goal",
        "priority",
        "owner_type",
        "owner_id",
        "tracker_issue_ref",
        "idempotency_key",
        "note_id",
        "trace_id",
        "reply_target",
        "reply_state",
        "retry_count",
        "kestra_execution_id",
        "original_task_id",
        "trigger",
        "reply_text",
        "roadmap_request_json",
    }
    updates = {key: value for key, value in payload.items() if key in allowed}
    if not updates:
        raise AgentTaskstateError("no updatable fields provided")
    if "kind" in updates:
        require_in(updates["kind"], TASK_KINDS, "kind")
    if "priority" in updates:
        require_in(updates["priority"], TASK_PRIORITIES, "priority")
    if "owner_type" in updates:
        require_in(updates["owner_type"], OWNER_TYPES, "owner_type")
    if "reply_state" in updates and updates["reply_state"] is not None:
        require_in(updates["reply_state"], REPLY_STATES, "reply_state")
    if "retry_count" in updates and (
        not isinstance(updates["retry_count"], int) or updates["retry_count"] < 0
    ):
        raise AgentTaskstateError("retry_count must be non-negative integer")
    if "tracker_issue_ref" in updates:
        updates["tracker_issue_ref"] = canonicalize_optional_ref(
            updates["tracker_issue_ref"], "tracker_issue_ref"
        )
    if "roadmap_request_json" in updates:
        updates["roadmap_request_json"] = _normalize_optional_json_text(
            updates["roadmap_request_json"]
        )
    with connect(ctx.db_path) as conn:
        init_db(conn)
        get_task(conn, args.task)
        if updates.get("parent_task_id"):
            get_task(conn, updates["parent_task_id"])
        updates["updated_at"] = now_utc()
        fields = ", ".join(f"{key} = ?" for key in updates)
        conn.execute(f"UPDATE tasks SET {fields} WHERE id = ?", [*updates.values(), args.task])
        row = get_task(conn, args.task)
    return json_ok({**row_to_task(row), "ref": task_ref(args.task)})


def cmd_task_set_status(ctx: AppContext, args: argparse.Namespace) -> int:
    require_in(args.to, TASK_STATUSES, "status")
    reason = getattr(args, "reason", None) or ""
    if getattr(args, "reason_required", False) and not reason:
        raise AgentTaskstateError("reason is required for this transition")
    actor_type = getattr(args, "actor_type", "system") or "system"
    actor_id = getattr(args, "actor_id", None)
    run_id = getattr(args, "run", None)
    with connect(ctx.db_path) as conn:
        init_db(conn)
        task = get_task(conn, args.task)
        try:
            validate_status_transition(conn, task, args.to)
            transition = StateTransitionService(conn).transition(
                args.task, args.to, reason, actor_type, actor_id, run_id
            )
        except (
            ServiceInvalidTransitionError,
            TerminalStateError,
            MissingReasonError,
            ValueError,
        ) as exc:
            raise _transition_error(exc) from exc
        row = get_task(conn, args.task)
    data: Dict[str, Any] = {**row_to_task(row), "ref": task_ref(args.task)}
    data["no_op"] = transition is None
    data["transition"] = (
        None
        if transition is None
        else {
            "id": transition.id,
            "from_status": transition.from_status,
            "to_status": transition.to_status,
            "reason": transition.reason,
            "actor_type": transition.actor_type,
            "actor_id": transition.actor_id,
            "run_id": transition.run_id,
            "changed_at": transition.changed_at,
        }
    )
    return json_ok(data)


def cmd_task_history(ctx: AppContext, args: argparse.Namespace) -> int:
    with connect(ctx.db_path) as conn:
        get_task(conn, args.task)
        history = StateTransitionService(conn).get_history(args.task)
    return json_ok(
        [
            {
                "id": item.id,
                "task_id": item.task_id,
                "from_status": item.from_status,
                "to_status": item.to_status,
                "reason": item.reason,
                "actor_type": item.actor_type,
                "actor_id": item.actor_id,
                "run_id": item.run_id,
                "changed_at": item.changed_at,
            }
            for item in history
        ]
    )

"""
CLI Task Commands
"""

from __future__ import annotations

import argparse
import sqlite3
from typing import Any, Dict, List

from ..constants import TASK_STATUSES
from ..db import connect, init_db
from ..errors import AgentTaskstateError
from ..fetch import get_task, get_task_state
from ..models import jdump, row_to_task, row_to_task_state
from ..typed_ref import task_ref
from ..utils import gen_id, now_utc
from ..validation import (
    _normalize_optional_json_text,
    load_json_arg,
    require_in,
    validate_status_transition,
    validate_task_payload,
)
from .. import AppContext


def cmd_init(ctx: AppContext, _args: argparse.Namespace) -> int:
    """Initialize database."""
    from ..utils import json_ok

    with connect(ctx.db_path) as conn:
        init_db(conn)
    return json_ok({"db_path": ctx.db_path, "initialized": True})


def cmd_task_create(ctx: AppContext, args: argparse.Namespace) -> int:
    """Create task."""
    from ..utils import json_ok

    payload = load_json_arg(args.json, args.file)
    validate_task_payload(payload)
    task_id = payload.get("id") or gen_id()
    now = now_utc()
    roadmap_request_json = _normalize_optional_json_text(payload.get("roadmap_request_json"))
    with connect(ctx.db_path) as conn:
        init_db(conn)
        if payload.get("parent_task_id"):
            get_task(conn, payload["parent_task_id"])
        conn.execute(
            """
            INSERT INTO tasks (
                id, parent_task_id, kind, title, goal, status, priority, owner_type, owner_id,
                idempotency_key, note_id, trace_id, reply_target, reply_state, retry_count,
                kestra_execution_id, original_task_id, trigger, reply_text, roadmap_request_json,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        row = get_task(conn, task_id)
    return json_ok({**row_to_task(row), "ref": task_ref(task_id)})


def cmd_task_show(ctx: AppContext, args: argparse.Namespace) -> int:
    """Show task."""
    from ..utils import json_ok
    from ..errors import NotFoundError

    with connect(ctx.db_path) as conn:
        row = get_task(conn, args.task)
        data = row_to_task(row)
        data["ref"] = task_ref(args.task)
        try:
            data["state"] = row_to_task_state(get_task_state(conn, args.task))
        except NotFoundError:
            data["state"] = None
    return json_ok(data)


def cmd_task_list(ctx: AppContext, args: argparse.Namespace) -> int:
    """List tasks."""
    from ..utils import json_ok

    clauses: List[str] = []
    params: List[Any] = []
    if args.status:
        clauses.append("status = ?")
        params.append(args.status)
    if args.kind:
        clauses.append("kind = ?")
        params.append(args.kind)
    if args.owner_type:
        clauses.append("owner_type = ?")
        params.append(args.owner_type)
    if args.owner_id:
        clauses.append("owner_id = ?")
        params.append(args.owner_id)
    if args.priority:
        clauses.append("priority = ?")
        params.append(args.priority)
    if getattr(args, "updated_before", None):
        clauses.append("updated_at < ?")
        params.append(args.updated_before)
    if getattr(args, "idempotency_key", None):
        clauses.append("idempotency_key = ?")
        params.append(args.idempotency_key)
    if getattr(args, "reply_state", None):
        clauses.append("reply_state = ?")
        params.append(args.reply_state)
    if getattr(args, "trace_id", None):
        clauses.append("trace_id = ?")
        params.append(args.trace_id)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"SELECT * FROM tasks {where} ORDER BY updated_at DESC, created_at DESC"
    with connect(ctx.db_path) as conn:
        init_db(conn)
        rows = conn.execute(sql, params).fetchall()
    data = [{**row_to_task(r), "ref": task_ref(r["id"])} for r in rows]
    return json_ok(data)


def cmd_task_update(ctx: AppContext, args: argparse.Namespace) -> int:
    """Update task."""
    from ..utils import json_ok
    from ..constants import TASK_KINDS, TASK_PRIORITIES, OWNER_TYPES, REPLY_STATES

    payload = load_json_arg(args.json, args.file)
    allowed = {
        "parent_task_id", "kind", "title", "goal", "priority", "owner_type", "owner_id",
        "idempotency_key", "note_id", "trace_id", "reply_target", "reply_state", "retry_count",
        "kestra_execution_id", "original_task_id", "trigger", "reply_text", "roadmap_request_json",
    }
    updates = {k: v for k, v in payload.items() if k in allowed}
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
    if "retry_count" in updates:
        if not isinstance(updates["retry_count"], int) or updates["retry_count"] < 0:
            raise AgentTaskstateError("retry_count must be non-negative integer")
    if "roadmap_request_json" in updates:
        updates["roadmap_request_json"] = _normalize_optional_json_text(updates["roadmap_request_json"])
    with connect(ctx.db_path) as conn:
        init_db(conn)
        get_task(conn, args.task)
        if updates.get("parent_task_id"):
            get_task(conn, updates["parent_task_id"])
        updates["updated_at"] = now_utc()
        fields = ", ".join([f"{k} = ?" for k in updates])
        conn.execute(f"UPDATE tasks SET {fields} WHERE id = ?", [*updates.values(), args.task])
        row = get_task(conn, args.task)
    return json_ok({**row_to_task(row), "ref": task_ref(args.task)})


def cmd_task_set_status(ctx: AppContext, args: argparse.Namespace) -> int:
    """Set task status."""
    from ..utils import json_ok

    require_in(args.to, TASK_STATUSES, "status")
    if args.to in {"archived", "in_progress"} and args.reason_required and not args.reason:
        raise AgentTaskstateError("reason is required for this transition")
    with connect(ctx.db_path) as conn:
        init_db(conn)
        row = get_task(conn, args.task)
        if row["status"] != args.to:
            validate_status_transition(conn, row, args.to)
        conn.execute("UPDATE tasks SET status = ?, updated_at = ? WHERE id = ?", (args.to, now_utc(), args.task))
        row = get_task(conn, args.task)
    data = {**row_to_task(row), "ref": task_ref(args.task)}
    if args.reason:
        data["transition_reason"] = args.reason
    return json_ok(data)
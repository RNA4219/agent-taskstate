"""
CLI Decision Commands
"""

from __future__ import annotations

import argparse
from typing import Any, List

from .. import AppContext
from ..constants import DECISION_STATUSES
from ..db import connect, init_db
from ..fetch import get_task, get_decision
from ..models import jdump, row_to_decision
from ..utils import gen_id, now_utc, json_ok
from ..validation import load_json_arg, require_in, validate_decision_payload


def cmd_decision_add(ctx: AppContext, args: argparse.Namespace) -> int:
    """Add decision."""
    payload = load_json_arg(args.json, args.file)
    validate_decision_payload(payload)
    decision_id = payload.get("id") or gen_id()
    now = now_utc()
    with connect(ctx.db_path) as conn:
        init_db(conn)
        get_task(conn, args.task)
        if payload.get("supersedes_decision_id"):
            get_decision(conn, payload["supersedes_decision_id"])
        conn.execute(
            """
            INSERT INTO decisions (
              id, task_id, summary, rationale, status, confidence, evidence_refs_json, supersedes_decision_id, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                decision_id,
                args.task,
                payload["summary"],
                payload.get("rationale"),
                payload.get("status", "proposed"),
                payload.get("confidence", "medium"),
                jdump(payload.get("evidence_refs", [])),
                payload.get("supersedes_decision_id"),
                now,
                now,
            ),
        )
        conn.execute("UPDATE tasks SET updated_at = ? WHERE id = ?", (now, args.task))
        row = get_decision(conn, decision_id)
    return json_ok(row_to_decision(row))


def cmd_decision_list(ctx: AppContext, args: argparse.Namespace) -> int:
    """List decisions."""
    sql = "SELECT * FROM decisions WHERE task_id = ?"
    params: List[Any] = [args.task]
    if args.status:
        sql += " AND status = ?"
        params.append(args.status)
    sql += " ORDER BY created_at DESC"
    with connect(ctx.db_path) as conn:
        rows = conn.execute(sql, params).fetchall()
    return json_ok([row_to_decision(r) for r in rows])


def _set_decision_status(ctx: AppContext, decision_id: str, status: str) -> int:
    """Set decision status."""
    require_in(status, DECISION_STATUSES, "decision.status")
    with connect(ctx.db_path) as conn:
        init_db(conn)
        get_decision(conn, decision_id)
        conn.execute(
            "UPDATE decisions SET status = ?, updated_at = ? WHERE id = ?",
            (status, now_utc(), decision_id),
        )
        row = get_decision(conn, decision_id)
    return json_ok(row_to_decision(row))


def cmd_decision_accept(ctx: AppContext, args: argparse.Namespace) -> int:
    """Accept decision."""
    return _set_decision_status(ctx, args.decision, "accepted")


def cmd_decision_reject(ctx: AppContext, args: argparse.Namespace) -> int:
    """Reject decision."""
    return _set_decision_status(ctx, args.decision, "rejected")

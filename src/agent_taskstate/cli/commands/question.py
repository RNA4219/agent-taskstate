"""
CLI Question Commands
"""

from __future__ import annotations

import argparse
from typing import Any, List

from .. import AppContext
from ..db import connect, init_db
from ..fetch import get_task, get_question
from ..models import jdump, row_to_question
from ..utils import gen_id, now_utc, json_ok
from ..validation import load_json_arg, validate_question_payload


def cmd_question_add(ctx: AppContext, args: argparse.Namespace) -> int:
    """Add question."""
    payload = load_json_arg(args.json, args.file)
    validate_question_payload(payload)
    qid = payload.get("id") or gen_id()
    now = now_utc()
    with connect(ctx.db_path) as conn:
        init_db(conn)
        get_task(conn, args.task)
        conn.execute(
            """
            INSERT INTO open_questions (
              id, task_id, question, priority, status, answer, evidence_refs_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                qid,
                args.task,
                payload["question"],
                payload.get("priority", "medium"),
                payload.get("status", "open"),
                payload.get("answer"),
                jdump(payload.get("evidence_refs", [])),
                now,
                now,
            ),
        )
        conn.execute("UPDATE tasks SET updated_at = ? WHERE id = ?", (now, args.task))
        row = get_question(conn, qid)
    return json_ok(row_to_question(row))


def cmd_question_list(ctx: AppContext, args: argparse.Namespace) -> int:
    """List questions."""
    sql = "SELECT * FROM open_questions WHERE task_id = ?"
    params: List[Any] = [args.task]
    if args.status:
        sql += " AND status = ?"
        params.append(args.status)
    if args.priority:
        sql += " AND priority = ?"
        params.append(args.priority)
    sql += " ORDER BY created_at DESC"
    with connect(ctx.db_path) as conn:
        rows = conn.execute(sql, params).fetchall()
    return json_ok([row_to_question(r) for r in rows])


def cmd_question_answer(ctx: AppContext, args: argparse.Namespace) -> int:
    """Answer question."""
    with connect(ctx.db_path) as conn:
        init_db(conn)
        get_question(conn, args.question)
        conn.execute(
            "UPDATE open_questions SET answer = ?, status = 'answered', updated_at = ? WHERE id = ?",
            (args.answer, now_utc(), args.question),
        )
        row = get_question(conn, args.question)
    return json_ok(row_to_question(row))


def cmd_question_defer(ctx: AppContext, args: argparse.Namespace) -> int:
    """Defer question."""
    with connect(ctx.db_path) as conn:
        init_db(conn)
        get_question(conn, args.question)
        answer = args.reason if args.reason else None
        conn.execute(
            "UPDATE open_questions SET answer = ?, status = 'deferred', updated_at = ? WHERE id = ?",
            (answer, now_utc(), args.question),
        )
        row = get_question(conn, args.question)
    return json_ok(row_to_question(row))

"""CLI run commands."""

from __future__ import annotations

import argparse
from typing import Any, List

from .. import AppContext
from ..constants import OWNER_TYPES, RUN_STATUSES, RUN_TYPES
from ..db import connect, init_db
from ..errors import ConflictError
from ..fetch import get_run, get_task
from ..utils import gen_id, now_utc, json_ok
from ..validation import canonicalize_optional_ref, require_in


def cmd_run_start(ctx: AppContext, args: argparse.Namespace) -> int:
    from ..models import row_to_run

    require_in(args.run_type, RUN_TYPES, "run_type")
    require_in(args.actor_type, OWNER_TYPES, "actor_type")
    input_ref = canonicalize_optional_ref(args.input_ref, "input_ref")
    now = now_utc()
    rid = gen_id()
    with connect(ctx.db_path) as conn:
        init_db(conn)
        get_task(conn, args.task)
        conn.execute(
            """
            INSERT INTO runs (
              id, task_id, actor_type, actor_id, run_type, status, input_ref, output_ref,
              started_at, ended_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 'running', ?, NULL, ?, NULL, ?, ?)
            """,
            (
                rid,
                args.task,
                args.actor_type,
                args.actor_id,
                args.run_type,
                input_ref,
                now,
                now,
                now,
            ),
        )
        row = get_run(conn, rid)
    return json_ok(row_to_run(row))


def cmd_run_list(ctx: AppContext, args: argparse.Namespace) -> int:
    from ..models import row_to_run

    sql = "SELECT * FROM runs WHERE task_id = ?"
    params: List[Any] = [args.task]
    if args.status:
        sql += " AND status = ?"
        params.append(args.status)
    sql += " ORDER BY created_at DESC"
    with connect(ctx.db_path) as conn:
        init_db(conn)
        get_task(conn, args.task)
        rows = conn.execute(sql, params).fetchall()
    return json_ok([row_to_run(row) for row in rows])


def cmd_run_finish(ctx: AppContext, args: argparse.Namespace) -> int:
    from ..models import row_to_run

    require_in(args.status, RUN_STATUSES - {"running"}, "run.status")
    output_ref = canonicalize_optional_ref(args.output_ref, "output_ref")
    now = now_utc()
    with connect(ctx.db_path) as conn:
        init_db(conn)
        row = get_run(conn, args.run)
        if row["status"] != "running":
            raise ConflictError("run is not in running state")
        conn.execute(
            "UPDATE runs SET status = ?, output_ref = ?, ended_at = ?, updated_at = ? WHERE id = ?",
            (args.status, output_ref, now, now, args.run),
        )
        row = get_run(conn, args.run)
    return json_ok(row_to_run(row))

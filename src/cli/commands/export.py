"""
CLI Export Commands
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .. import AppContext
from ..db import connect
from ..errors import NotFoundError
from ..fetch import get_task, get_task_state
from ..models import row_to_task, row_to_task_state, row_to_decision, row_to_question, row_to_run, row_to_bundle
from ..typed_ref import task_ref
from ..utils import now_utc, json_ok


def cmd_export_task(ctx: AppContext, args: argparse.Namespace) -> int:
    """Export task to JSON file."""
    with connect(ctx.db_path) as conn:
        task = row_to_task(get_task(conn, args.task))
        try:
            state = row_to_task_state(get_task_state(conn, args.task))
        except NotFoundError:
            state = None
        decisions = [
            row_to_decision(r)
            for r in conn.execute("SELECT * FROM decisions WHERE task_id = ? ORDER BY created_at ASC", (args.task,)).fetchall()
        ]
        questions = [
            row_to_question(r)
            for r in conn.execute("SELECT * FROM open_questions WHERE task_id = ? ORDER BY created_at ASC", (args.task,)).fetchall()
        ]
        runs = [row_to_run(r) for r in conn.execute("SELECT * FROM runs WHERE task_id = ? ORDER BY created_at ASC", (args.task,)).fetchall()]
        bundles = [
            row_to_bundle(r)
            for r in conn.execute("SELECT * FROM context_bundles WHERE task_id = ? ORDER BY created_at ASC", (args.task,)).fetchall()
        ]
    export = {
        "task": {**task, "ref": task_ref(task["id"])},
        "task_state": state,
        "decisions": decisions,
        "open_questions": questions,
        "runs": runs,
        "context_bundles": bundles,
        "exported_at": now_utc(),
    }
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(export, ensure_ascii=False, indent=2), encoding="utf-8")
    return json_ok({"task": args.task, "output": args.output})
"""
CLI Context Bundle Commands
"""

from __future__ import annotations

import argparse
from typing import Any, Dict, List

from .. import AppContext
from ..constants import BUILD_REASONS, EXPECTED_OUTPUT_SCHEMA
from ..db import connect, init_db
from ..fetch import get_task, get_task_state, get_bundle
from ..models import jdump, row_to_task, row_to_task_state, row_to_decision, row_to_question, row_to_bundle
from ..typed_ref import task_ref
from ..utils import gen_id, now_utc, json_ok
from ..validation import require_in


def should_include_evidence(
    state: Dict[str, Any],
    build_reason: str,
    decisions: List[Dict[str, Any]],
    questions: List[Dict[str, Any]],
) -> bool:
    """Determine if evidence should be included in bundle."""
    if state.get("confidence") == "low":
        return True
    if build_reason == "review":
        return True
    if state.get("current_step") in {"investigation", "verification"}:
        return True
    if state.get("context_policy", {}).get("force_evidence") is True:
        return True
    if any(d.get("confidence") == "low" for d in decisions):
        return True
    if any(q.get("priority") == "high" and q.get("status") == "open" for q in questions):
        return True
    return False


def cmd_context_build(ctx: AppContext, args: argparse.Namespace) -> int:
    """Build context bundle."""
    require_in(args.reason, BUILD_REASONS, "build_reason")
    now = now_utc()
    bid = gen_id()
    with connect(ctx.db_path) as conn:
        init_db(conn)
        task = row_to_task(get_task(conn, args.task))
        state = row_to_task_state(get_task_state(conn, args.task))
        drows = conn.execute(
            "SELECT * FROM decisions WHERE task_id = ? AND status IN ('accepted', 'proposed') ORDER BY created_at ASC",
            (args.task,),
        ).fetchall()
        qrows = conn.execute(
            "SELECT * FROM open_questions WHERE task_id = ? AND status = 'open' ORDER BY created_at ASC",
            (args.task,),
        ).fetchall()
        decisions = [row_to_decision(r) for r in drows]
        questions = [row_to_question(r) for r in qrows]

        accepted_decisions = [d for d in decisions if d["status"] == "accepted"]
        proposed_decisions = [d for d in decisions if d["status"] == "proposed"]
        include_evidence = should_include_evidence(state, args.reason, decisions, questions)

        decision_refs = [d["ref"] for d in accepted_decisions] + [d["ref"] for d in proposed_decisions]
        question_refs = [q["ref"] for q in questions]
        artifact_refs = list(state.get("artifact_refs", []))
        evidence_refs = list(state.get("evidence_refs", [])) if include_evidence else []

        state_snapshot = {
            "task": task,
            "task_ref": task_ref(task["id"]),
            "task_state": state,
            "accepted_decisions": accepted_decisions,
            "open_questions": questions,
            "done_when": state["done_when"],
            "current_step": state["current_step"],
            "build_reason": args.reason,
        }

        conn.execute(
            """
            INSERT INTO context_bundles (
              id, task_id, build_reason, state_snapshot_json, included_decision_refs_json,
              included_open_question_refs_json, included_artifact_refs_json, included_evidence_refs_json,
              expected_output_schema_json, created_at, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                bid,
                args.task,
                args.reason,
                jdump(state_snapshot),
                jdump(decision_refs),
                jdump(question_refs),
                jdump(artifact_refs),
                jdump(evidence_refs),
                jdump(EXPECTED_OUTPUT_SCHEMA),
                now,
                jdump({"include_evidence": include_evidence}),
            ),
        )
        row = get_bundle(conn, bid)
    return json_ok(row_to_bundle(row))


def cmd_context_show(ctx: AppContext, args: argparse.Namespace) -> int:
    """Show context bundle."""
    with connect(ctx.db_path) as conn:
        row = get_bundle(conn, args.bundle)
    return json_ok(row_to_bundle(row))
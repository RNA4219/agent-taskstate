"""Task state commands with insert-only put and atomic CAS patch."""

from __future__ import annotations

import argparse
from typing import Any, Dict

from .. import AppContext
from ..db import connect, init_db
from ..errors import AgentTaskstateError, ConflictError
from ..fetch import get_task, get_task_state
from ..models import jdump, row_to_task_state
from ..utils import now_utc, json_ok
from ..validation import canonicalize_refs, load_json_arg, validate_state_payload


def cmd_state_get(ctx: AppContext, args: argparse.Namespace) -> int:
    with connect(ctx.db_path) as conn:
        row = get_task_state(conn, args.task)
    return json_ok(row_to_task_state(row))


def cmd_state_put(ctx: AppContext, args: argparse.Namespace) -> int:
    payload = normalize_state_payload(load_json_arg(args.json, args.file))
    now = now_utc()
    with connect(ctx.db_path) as conn:
        init_db(conn)
        get_task(conn, args.task)
        if conn.execute("SELECT 1 FROM task_states WHERE task_id = ?", (args.task,)).fetchone():
            raise ConflictError("task state already exists; use state patch")
        conn.execute(
            """
            INSERT INTO task_states (
              task_id, revision, current_step, constraints_json, done_when_json, current_summary,
              artifact_refs_json, evidence_refs_json, confidence, context_policy_json,
              created_at, updated_at
            ) VALUES (?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                args.task,
                payload["current_step"],
                jdump(payload["constraints"]),
                jdump(payload["done_when"]),
                payload["current_summary"],
                jdump(payload["artifact_refs"]),
                jdump(payload["evidence_refs"]),
                payload["confidence"],
                jdump(payload["context_policy"]),
                now,
                now,
            ),
        )
        conn.execute("UPDATE tasks SET updated_at = ? WHERE id = ?", (now, args.task))
        row = get_task_state(conn, args.task)
    return json_ok(row_to_task_state(row))


def cmd_state_patch(ctx: AppContext, args: argparse.Namespace) -> int:
    patch = load_json_arg(args.json, args.file)
    if args.expected_revision is None:
        raise AgentTaskstateError("--expected-revision is required")
    with connect(ctx.db_path) as conn:
        init_db(conn)
        get_task(conn, args.task)
        current = get_task_state(conn, args.task)
        state = row_to_task_state(current)
        merged = {
            "current_step": state["current_step"],
            "constraints": state["constraints"],
            "done_when": state["done_when"],
            "current_summary": state["current_summary"],
            "artifact_refs": state["artifact_refs"],
            "evidence_refs": state["evidence_refs"],
            "confidence": state["confidence"],
            "context_policy": state["context_policy"],
        }
        merged.update(patch)
        normalized = normalize_state_payload(merged)
        now = now_utc()
        result = conn.execute(
            """
            UPDATE task_states
            SET revision = revision + 1, current_step = ?, constraints_json = ?,
                done_when_json = ?, current_summary = ?, artifact_refs_json = ?,
                evidence_refs_json = ?, confidence = ?, context_policy_json = ?, updated_at = ?
            WHERE task_id = ? AND revision = ?
            """,
            (
                normalized["current_step"],
                jdump(normalized["constraints"]),
                jdump(normalized["done_when"]),
                normalized["current_summary"],
                jdump(normalized["artifact_refs"]),
                jdump(normalized["evidence_refs"]),
                normalized["confidence"],
                jdump(normalized["context_policy"]),
                now,
                args.task,
                args.expected_revision,
            ),
        )
        if result.rowcount != 1:
            raise ConflictError("revision mismatch")
        conn.execute("UPDATE tasks SET updated_at = ? WHERE id = ?", (now, args.task))
        row = get_task_state(conn, args.task)
    return json_ok(row_to_task_state(row))


def normalize_state_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    normalized = {
        "current_step": payload["current_step"],
        "constraints": payload.get("constraints", []),
        "done_when": payload.get("done_when", []),
        "current_summary": payload.get("current_summary"),
        "artifact_refs": payload.get("artifact_refs", []),
        "evidence_refs": payload.get("evidence_refs", []),
        "confidence": payload.get("confidence", "medium"),
        "context_policy": payload.get("context_policy", {}),
    }
    validate_state_payload(normalized)
    normalized["artifact_refs"] = canonicalize_refs(normalized["artifact_refs"], "artifact_refs")
    normalized["evidence_refs"] = canonicalize_refs(normalized["evidence_refs"], "evidence_refs")
    return normalized

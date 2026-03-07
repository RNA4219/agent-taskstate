"""
Test helper functions for agent-taskstate CLI testing.
"""

import argparse
import importlib.util
import io
import json
import sqlite3
import sys
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any, Dict

# Load CLI module from file (filename contains hyphen)
_cli_path = Path(__file__).parent.parent / "docs" / "src" / "agent-taskstate_cli.py"
_spec = importlib.util.spec_from_file_location("agent_taskstate", _cli_path)
agent_taskstate = importlib.util.module_from_spec(_spec)
sys.modules["agent_taskstate"] = agent_taskstate
_spec.loader.exec_module(agent_taskstate)


# ============================================
# Helper Functions
# ============================================

def make_args(**kwargs) -> argparse.Namespace:
    """Create argparse.Namespace from kwargs."""
    return argparse.Namespace(**kwargs)


def capture_output(func, *args, **kwargs) -> Dict[str, Any]:
    """Run a function and capture its JSON output."""
    stdout_capture = io.StringIO()
    with redirect_stdout(stdout_capture):
        try:
            func(*args, **kwargs)
        except agent_taskstate.AgentTaskstateError as e:
            # Exception was raised before output was printed - construct error output
            return {"ok": False, "data": None, "error": {"code": e.code, "message": str(e)}}
    output = stdout_capture.getvalue()
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        return {"ok": False, "raw_output": output}


# ============================================
# Database Helper Functions
# ============================================

def create_task(
    conn: sqlite3.Connection,
    task_id: str = None,
    kind: str = "feature",
    title: str = "Test Task",
    goal: str = "Test Goal",
    status: str = "draft",
    priority: str = "high",
    owner_type: str = "agent",
    owner_id: str = "agent-001",
    parent_task_id: str = None,
) -> str:
    """Create a task directly in the database."""
    if task_id is None:
        task_id = agent_taskstate.gen_id()
    now = agent_taskstate.now_utc()
    conn.execute(
        """
        INSERT INTO tasks (id, parent_task_id, kind, title, goal, status, priority, owner_type, owner_id, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (task_id, parent_task_id, kind, title, goal, status, priority, owner_type, owner_id, now, now),
    )
    return task_id


def create_task_state(
    conn: sqlite3.Connection,
    task_id: str,
    revision: int = 1,
    current_step: str = "初期状態",
    constraints: list = None,
    done_when: list = None,
    current_summary: str = "",
    artifact_refs: list = None,
    evidence_refs: list = None,
    confidence: str = "medium",
    context_policy: dict = None,
) -> None:
    """Create a task_state directly in the database."""
    now = agent_taskstate.now_utc()
    conn.execute(
        """
        INSERT INTO task_states (task_id, revision, current_step, constraints_json, done_when_json,
                                 current_summary, artifact_refs_json, evidence_refs_json,
                                 confidence, context_policy_json, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            task_id,
            revision,
            current_step,
            agent_taskstate.jdump(constraints or []),
            agent_taskstate.jdump(done_when or []),
            current_summary,
            agent_taskstate.jdump(artifact_refs or []),
            agent_taskstate.jdump(evidence_refs or []),
            confidence,
            agent_taskstate.jdump(context_policy or {}),
            now,
            now,
        ),
    )


def create_decision(
    conn: sqlite3.Connection,
    task_id: str,
    decision_id: str = None,
    summary: str = "Test Decision",
    rationale: str = "",
    status: str = "proposed",
    confidence: str = "medium",
    evidence_refs: list = None,
    supersedes_decision_id: str = None,
) -> str:
    """Create a decision directly in the database."""
    if decision_id is None:
        decision_id = agent_taskstate.gen_id()
    now = agent_taskstate.now_utc()
    conn.execute(
        """
        INSERT INTO decisions (id, task_id, summary, rationale, status, confidence,
                               evidence_refs_json, supersedes_decision_id, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            decision_id,
            task_id,
            summary,
            rationale,
            status,
            confidence,
            agent_taskstate.jdump(evidence_refs or []),
            supersedes_decision_id,
            now,
            now,
        ),
    )
    return decision_id


def create_open_question(
    conn: sqlite3.Connection,
    task_id: str,
    question_id: str = None,
    question: str = "Test Question?",
    priority: str = "medium",
    status: str = "open",
    answer: str = None,
    evidence_refs: list = None,
) -> str:
    """Create an open_question directly in the database."""
    if question_id is None:
        question_id = agent_taskstate.gen_id()
    now = agent_taskstate.now_utc()
    conn.execute(
        """
        INSERT INTO open_questions (id, task_id, question, priority, status, answer, evidence_refs_json, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            question_id,
            task_id,
            question,
            priority,
            status,
            answer,
            agent_taskstate.jdump(evidence_refs or []),
            now,
            now,
        ),
    )
    return question_id


def create_run(
    conn: sqlite3.Connection,
    task_id: str,
    run_id: str = None,
    actor_type: str = "agent",
    actor_id: str = "agent-001",
    run_type: str = "execute",
    status: str = "running",
    input_ref: str = None,
    output_ref: str = None,
    ended_at: str = None,
) -> str:
    """Create a run directly in the database."""
    if run_id is None:
        run_id = agent_taskstate.gen_id()
    now = agent_taskstate.now_utc()
    conn.execute(
        """
        INSERT INTO runs (id, task_id, actor_type, actor_id, run_type, status, input_ref, output_ref, started_at, ended_at, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (run_id, task_id, actor_type, actor_id, run_type, status, input_ref, output_ref, now, ended_at, now, now),
    )
    return run_id


def create_context_bundle(
    conn: sqlite3.Connection,
    task_id: str,
    bundle_id: str = None,
    build_reason: str = "normal",
    state_snapshot: dict = None,
) -> str:
    """Create a context_bundle directly in the database."""
    if bundle_id is None:
        bundle_id = agent_taskstate.gen_id()
    now = agent_taskstate.now_utc()
    conn.execute(
        """
        INSERT INTO context_bundles (id, task_id, build_reason, state_snapshot_json,
                                     included_decision_refs_json, included_open_question_refs_json,
                                     included_artifact_refs_json, included_evidence_refs_json,
                                     expected_output_schema_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            bundle_id,
            task_id,
            build_reason,
            agent_taskstate.jdump(state_snapshot or {}),
            agent_taskstate.jdump([]),
            agent_taskstate.jdump([]),
            agent_taskstate.jdump([]),
            agent_taskstate.jdump([]),
            agent_taskstate.jdump(agent_taskstate.EXPECTED_OUTPUT_SCHEMA),
            now,
        ),
    )
    return bundle_id


# ============================================
# CLI Command Wrappers
# ============================================

def cmd_task_create(ctx, kind, title, goal, priority, owner_type, owner_id, parent_task_id=None) -> Dict:
    """Wrapper for task create command."""
    payload = {
        "kind": kind,
        "title": title,
        "goal": goal,
        "priority": priority,
        "owner_type": owner_type,
        "owner_id": owner_id,
    }
    if parent_task_id:
        payload["parent_task_id"] = parent_task_id
    args = make_args(json=json.dumps(payload), file=None)
    return capture_output(agent_taskstate.cmd_task_create, ctx, args)


def cmd_task_show(ctx, task_id) -> Dict:
    """Wrapper for task show command."""
    args = make_args(task=task_id)
    return capture_output(agent_taskstate.cmd_task_show, ctx, args)


def cmd_task_list(ctx, status=None, kind=None, owner_type=None, owner_id=None) -> Dict:
    """Wrapper for task list command."""
    args = make_args(status=status, kind=kind, owner_type=owner_type, owner_id=owner_id, priority=None)
    return capture_output(agent_taskstate.cmd_task_list, ctx, args)


def cmd_task_update(ctx, task_id, title=None, goal=None, priority=None) -> Dict:
    """Wrapper for task update command."""
    payload = {}
    if title is not None:
        payload["title"] = title
    if goal is not None:
        payload["goal"] = goal
    if priority is not None:
        payload["priority"] = priority
    args = make_args(task=task_id, json=json.dumps(payload), file=None)
    return capture_output(agent_taskstate.cmd_task_update, ctx, args)


def cmd_task_set_status(ctx, task_id, to_status, reason=None) -> Dict:
    """Wrapper for task set-status command."""
    args = make_args(task=task_id, to=to_status, reason=reason, reason_required=True)
    return capture_output(agent_taskstate.cmd_task_set_status, ctx, args)


def cmd_state_put(ctx, task_id, state_json) -> Dict:
    """Wrapper for state put command."""
    args = make_args(task=task_id, json=json.dumps(state_json), file=None)
    return capture_output(agent_taskstate.cmd_state_put, ctx, args)


def cmd_state_get(ctx, task_id) -> Dict:
    """Wrapper for state get command."""
    args = make_args(task=task_id)
    return capture_output(agent_taskstate.cmd_state_get, ctx, args)


def cmd_state_patch(ctx, task_id, expected_revision, patch_json) -> Dict:
    """Wrapper for state patch command."""
    args = make_args(task=task_id, expected_revision=expected_revision,
                     json=json.dumps(patch_json), file=None)
    return capture_output(agent_taskstate.cmd_state_patch, ctx, args)


def cmd_decision_add(ctx, task_id, decision_json) -> Dict:
    """Wrapper for decision add command."""
    args = make_args(task=task_id, json=json.dumps(decision_json), file=None)
    return capture_output(agent_taskstate.cmd_decision_add, ctx, args)


def cmd_decision_list(ctx, task_id, status=None) -> Dict:
    """Wrapper for decision list command."""
    args = make_args(task=task_id, status=status)
    return capture_output(agent_taskstate.cmd_decision_list, ctx, args)


def cmd_decision_accept(ctx, decision_id) -> Dict:
    """Wrapper for decision accept command."""
    args = make_args(decision=decision_id)
    return capture_output(agent_taskstate.cmd_decision_accept, ctx, args)


def cmd_decision_reject(ctx, decision_id) -> Dict:
    """Wrapper for decision reject command."""
    args = make_args(decision=decision_id)
    return capture_output(agent_taskstate.cmd_decision_reject, ctx, args)


def cmd_question_add(ctx, task_id, question_json) -> Dict:
    """Wrapper for question add command."""
    args = make_args(task=task_id, json=json.dumps(question_json), file=None)
    return capture_output(agent_taskstate.cmd_question_add, ctx, args)


def cmd_question_list(ctx, task_id, status=None, priority=None) -> Dict:
    """Wrapper for question list command."""
    args = make_args(task=task_id, status=status, priority=priority)
    return capture_output(agent_taskstate.cmd_question_list, ctx, args)


def cmd_question_answer(ctx, question_id, answer) -> Dict:
    """Wrapper for question answer command."""
    args = make_args(question=question_id, answer=answer)
    return capture_output(agent_taskstate.cmd_question_answer, ctx, args)


def cmd_question_defer(ctx, question_id, reason=None) -> Dict:
    """Wrapper for question defer command."""
    args = make_args(question=question_id, reason=reason)
    return capture_output(agent_taskstate.cmd_question_defer, ctx, args)


def cmd_run_start(ctx, task_id, run_type, actor_type, actor_id, input_ref=None) -> Dict:
    """Wrapper for run start command."""
    args = make_args(task=task_id, run_type=run_type, actor_type=actor_type,
                     actor_id=actor_id, input_ref=input_ref)
    return capture_output(agent_taskstate.cmd_run_start, ctx, args)


def cmd_run_finish(ctx, run_id, status, output_ref=None) -> Dict:
    """Wrapper for run finish command."""
    args = make_args(run=run_id, status=status, output_ref=output_ref)
    return capture_output(agent_taskstate.cmd_run_finish, ctx, args)


def cmd_run_list(ctx, task_id, status=None) -> Dict:
    """Wrapper for run list command."""
    # Note: CLI doesn't have cmd_run_list, this is a placeholder
    # Tests using this should be skipped or the CLI needs to implement this
    raise NotImplementedError("cmd_run_list is not implemented in the CLI")


def cmd_context_build(ctx, task_id, build_reason) -> Dict:
    """Wrapper for context build command."""
    args = make_args(task=task_id, reason=build_reason)
    return capture_output(agent_taskstate.cmd_context_build, ctx, args)


def cmd_context_show(ctx, bundle_id) -> Dict:
    """Wrapper for context show command."""
    args = make_args(bundle=bundle_id)
    return capture_output(agent_taskstate.cmd_context_show, ctx, args)


def cmd_export_task(ctx, task_id, output_path) -> Dict:
    """Wrapper for export task command."""
    args = make_args(task=task_id, output=output_path)
    return capture_output(agent_taskstate.cmd_export_task, ctx, args)


__all__ = [
    "agent_taskstate",
    "make_args",
    "capture_output",
    "create_task",
    "create_task_state",
    "create_decision",
    "create_open_question",
    "create_run",
    "create_context_bundle",
    "cmd_task_create",
    "cmd_task_show",
    "cmd_task_list",
    "cmd_task_update",
    "cmd_task_set_status",
    "cmd_state_put",
    "cmd_state_get",
    "cmd_state_patch",
    "cmd_decision_add",
    "cmd_decision_list",
    "cmd_decision_accept",
    "cmd_decision_reject",
    "cmd_question_add",
    "cmd_question_list",
    "cmd_question_answer",
    "cmd_question_defer",
    "cmd_run_start",
    "cmd_run_finish",
    "cmd_run_list",
    "cmd_context_build",
    "cmd_context_show",
    "cmd_export_task",
]
"""Argument parser for the canonical CLI."""

from __future__ import annotations

import argparse
import os

from .constants import APP_NAME, DEFAULT_DB_PATH
from .commands import (
    cmd_context_build,
    cmd_context_show,
    cmd_decision_accept,
    cmd_decision_add,
    cmd_decision_list,
    cmd_decision_reject,
    cmd_export_task,
    cmd_init,
    cmd_question_add,
    cmd_question_answer,
    cmd_question_defer,
    cmd_question_list,
    cmd_run_finish,
    cmd_run_list,
    cmd_run_start,
    cmd_state_get,
    cmd_state_patch,
    cmd_state_put,
    cmd_task_create,
    cmd_task_history,
    cmd_task_list,
    cmd_task_set_status,
    cmd_task_show,
    cmd_task_update,
    cmd_tracker_connection_add,
    cmd_tracker_events,
    cmd_tracker_fetch,
    cmd_tracker_link,
    cmd_tracker_snapshot,
    cmd_tracker_suggest,
    cmd_tracker_comment,
    cmd_tracker_status,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=APP_NAME, description="agent-taskstate CLI")
    parser.add_argument("--db", default=os.environ.get("AGENT_TASKSTATE_DB", DEFAULT_DB_PATH))
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("init", help="initialize SQLite database")
    p.set_defaults(func=cmd_init)

    task = sub.add_parser("task", help="task commands")
    tasks = task.add_subparsers(dest="task_command")
    p = tasks.add_parser("create")
    p.add_argument("--json")
    p.add_argument("--file")
    p.set_defaults(func=cmd_task_create)
    p = tasks.add_parser("show")
    p.add_argument("--task", required=True)
    p.set_defaults(func=cmd_task_show)
    p = tasks.add_parser("list")
    for name in (
        "status",
        "kind",
        "owner-type",
        "owner-id",
        "priority",
        "updated-before",
        "idempotency-key",
        "reply-state",
        "trace-id",
    ):
        p.add_argument(f"--{name}")
    p.set_defaults(func=cmd_task_list)
    p = tasks.add_parser("update")
    p.add_argument("--task", required=True)
    p.add_argument("--json")
    p.add_argument("--file")
    p.set_defaults(func=cmd_task_update)
    p = tasks.add_parser("set-status")
    p.add_argument("--task", required=True)
    p.add_argument("--to", required=True)
    p.add_argument("--reason")
    p.add_argument("--actor-type", default="system")
    p.add_argument("--actor-id")
    p.add_argument("--run")
    p.add_argument("--reason-required", action="store_true", default=False)
    p.set_defaults(func=cmd_task_set_status)
    p = tasks.add_parser("history")
    p.add_argument("--task", required=True)
    p.set_defaults(func=cmd_task_history)

    state = sub.add_parser("state", help="task state commands")
    states = state.add_subparsers(dest="state_command")
    p = states.add_parser("get")
    p.add_argument("--task", required=True)
    p.set_defaults(func=cmd_state_get)
    p = states.add_parser("put")
    p.add_argument("--task", required=True)
    p.add_argument("--json")
    p.add_argument("--file")
    p.set_defaults(func=cmd_state_put)
    p = states.add_parser("patch")
    p.add_argument("--task", required=True)
    p.add_argument("--json")
    p.add_argument("--file")
    p.add_argument("--expected-revision", required=True, type=int)
    p.set_defaults(func=cmd_state_patch)

    decision = sub.add_parser("decision", help="decision commands")
    decisions = decision.add_subparsers(dest="decision_command")
    p = decisions.add_parser("add")
    p.add_argument("--task", required=True)
    p.add_argument("--json")
    p.add_argument("--file")
    p.set_defaults(func=cmd_decision_add)
    p = decisions.add_parser("list")
    p.add_argument("--task", required=True)
    p.add_argument("--status")
    p.set_defaults(func=cmd_decision_list)
    p = decisions.add_parser("accept")
    p.add_argument("--decision", required=True)
    p.set_defaults(func=cmd_decision_accept)
    p = decisions.add_parser("reject")
    p.add_argument("--decision", required=True)
    p.set_defaults(func=cmd_decision_reject)

    question = sub.add_parser("question", help="question commands")
    questions = question.add_subparsers(dest="question_command")
    p = questions.add_parser("add")
    p.add_argument("--task", required=True)
    p.add_argument("--json")
    p.add_argument("--file")
    p.set_defaults(func=cmd_question_add)
    p = questions.add_parser("list")
    p.add_argument("--task", required=True)
    p.add_argument("--status")
    p.add_argument("--priority")
    p.set_defaults(func=cmd_question_list)
    p = questions.add_parser("answer")
    p.add_argument("--question", required=True)
    p.add_argument("--answer", required=True)
    p.set_defaults(func=cmd_question_answer)
    p = questions.add_parser("defer")
    p.add_argument("--question", required=True)
    p.add_argument("--reason")
    p.set_defaults(func=cmd_question_defer)

    run = sub.add_parser("run", help="run commands")
    runs = run.add_subparsers(dest="run_command")
    p = runs.add_parser("start")
    p.add_argument("--task", required=True)
    p.add_argument("--run-type", required=True)
    p.add_argument("--actor-type", default="system")
    p.add_argument("--actor-id")
    p.add_argument("--input-ref")
    p.set_defaults(func=cmd_run_start)
    p = runs.add_parser("list")
    p.add_argument("--task", required=True)
    p.add_argument("--status")
    p.set_defaults(func=cmd_run_list)
    p = runs.add_parser("finish")
    p.add_argument("--run", required=True)
    p.add_argument("--status", required=True)
    p.add_argument("--output-ref")
    p.set_defaults(func=cmd_run_finish)

    context = sub.add_parser("context", help="context bundle commands")
    contexts = context.add_subparsers(dest="context_command")
    p = contexts.add_parser("build")
    p.add_argument("--task", required=True)
    p.add_argument("--reason", default="normal")
    p.add_argument("--purpose", default="continue_work")
    p.add_argument("--rebuild-level", default="L2")
    p.add_argument("--include-raw", action="store_true")
    p.set_defaults(func=cmd_context_build)
    p = contexts.add_parser("show")
    p.add_argument("--bundle", required=True)
    p.set_defaults(func=cmd_context_show)

    export = sub.add_parser("export", help="export commands")
    exports = export.add_subparsers(dest="export_command")
    p = exports.add_parser("task")
    p.add_argument("--task", required=True)
    p.add_argument("--output", required=True)
    p.set_defaults(func=cmd_export_task)

    tracker = sub.add_parser("tracker", help="explicit tracker operations")
    trackers = tracker.add_subparsers(dest="tracker_command")
    connection = trackers.add_parser("connection")
    connections = connection.add_subparsers(dest="connection_command")
    p = connections.add_parser("add")
    p.add_argument("--provider", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--json")
    p.add_argument("--file")
    p.add_argument("--secret-env-json")
    p.set_defaults(func=cmd_tracker_connection_add)
    p = trackers.add_parser("fetch")
    p.add_argument("--connection", required=True)
    p.add_argument("--issue-key", required=True)
    p.set_defaults(func=cmd_tracker_fetch)
    p = trackers.add_parser("link")
    p.add_argument("--issue-ref", required=True)
    p.add_argument("--task", required=True)
    p.add_argument("--role", default="primary")
    p.set_defaults(func=cmd_tracker_link)
    p = trackers.add_parser("snapshot")
    p.add_argument("--issue-ref", required=True)
    p.set_defaults(func=cmd_tracker_snapshot)
    p = trackers.add_parser("events")
    p.add_argument("--connection")
    p.add_argument("--issue-ref")
    p.add_argument("--limit", type=int, default=100)
    p.set_defaults(func=cmd_tracker_events)
    p = trackers.add_parser("suggest")
    p.add_argument("--issue-ref", required=True)
    p.set_defaults(func=cmd_tracker_suggest)
    p = trackers.add_parser("comment")
    p.add_argument("--connection", required=True)
    p.add_argument("--issue-key", required=True)
    p.add_argument("--comment", required=True)
    p.set_defaults(func=cmd_tracker_comment)
    p = trackers.add_parser("status")
    p.add_argument("--connection", required=True)
    p.add_argument("--issue-key", required=True)
    p.add_argument("--status", required=True)
    p.set_defaults(func=cmd_tracker_status)

    return parser

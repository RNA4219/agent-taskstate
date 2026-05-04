"""
CLI Argument Parser
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from .constants import APP_NAME, DEFAULT_DB_PATH
from .commands import (
    cmd_init,
    cmd_task_create,
    cmd_task_show,
    cmd_task_list,
    cmd_task_update,
    cmd_task_set_status,
    cmd_state_get,
    cmd_state_put,
    cmd_state_patch,
    cmd_decision_add,
    cmd_decision_list,
    cmd_decision_accept,
    cmd_decision_reject,
    cmd_question_add,
    cmd_question_list,
    cmd_question_answer,
    cmd_question_defer,
    cmd_run_start,
    cmd_run_list,
    cmd_run_finish,
    cmd_context_build,
    cmd_context_show,
    cmd_export_task,
)


def build_parser() -> argparse.ArgumentParser:
    """Build CLI argument parser."""
    parser = argparse.ArgumentParser(prog=APP_NAME, description="agent-taskstate CLI")
    parser.add_argument(
        "--db",
        default=os.environ.get("AGENT_TASKSTATE_DB", DEFAULT_DB_PATH),
        help="SQLite DB path",
    )

    sub = parser.add_subparsers(dest="command")

    # init
    p_init = sub.add_parser("init", help="initialize SQLite database")
    p_init.set_defaults(func=cmd_init)

    # task
    p_task = sub.add_parser("task", help="task commands")
    sp_task = p_task.add_subparsers(dest="task_command")

    p_task_create = sp_task.add_parser("create", help="create task")
    p_task_create.add_argument("--json")
    p_task_create.add_argument("--file")
    p_task_create.set_defaults(func=cmd_task_create)

    p_task_show = sp_task.add_parser("show", help="show task")
    p_task_show.add_argument("--task", required=True)
    p_task_show.set_defaults(func=cmd_task_show)

    p_task_list = sp_task.add_parser("list", help="list tasks")
    p_task_list.add_argument("--status")
    p_task_list.add_argument("--kind")
    p_task_list.add_argument("--owner-type")
    p_task_list.add_argument("--owner-id")
    p_task_list.add_argument("--priority")
    p_task_list.add_argument("--updated-before")
    p_task_list.add_argument("--idempotency-key")
    p_task_list.add_argument("--reply-state")
    p_task_list.add_argument("--trace-id")
    p_task_list.set_defaults(func=cmd_task_list)

    p_task_update = sp_task.add_parser("update", help="update task")
    p_task_update.add_argument("--task", required=True)
    p_task_update.add_argument("--json")
    p_task_update.add_argument("--file")
    p_task_update.set_defaults(func=cmd_task_update)

    p_task_status = sp_task.add_parser("set-status", help="set task status")
    p_task_status.add_argument("--task", required=True)
    p_task_status.add_argument("--to", required=True)
    p_task_status.add_argument("--reason")
    p_task_status.add_argument("--reason-required", action="store_true", default=False)
    p_task_status.set_defaults(func=cmd_task_set_status)

    # state
    p_state = sub.add_parser("state", help="task state commands")
    sp_state = p_state.add_subparsers(dest="state_command")

    p_state_get = sp_state.add_parser("get")
    p_state_get.add_argument("--task", required=True)
    p_state_get.set_defaults(func=cmd_state_get)

    p_state_put = sp_state.add_parser("put")
    p_state_put.add_argument("--task", required=True)
    p_state_put.add_argument("--json")
    p_state_put.add_argument("--file")
    p_state_put.set_defaults(func=cmd_state_put)

    p_state_patch = sp_state.add_parser("patch")
    p_state_patch.add_argument("--task", required=True)
    p_state_patch.add_argument("--json")
    p_state_patch.add_argument("--file")
    p_state_patch.add_argument("--expected-revision", required=True, type=int)
    p_state_patch.set_defaults(func=cmd_state_patch)

    # decision
    p_decision = sub.add_parser("decision", help="decision commands")
    sp_decision = p_decision.add_subparsers(dest="decision_command")

    p_dec_add = sp_decision.add_parser("add")
    p_dec_add.add_argument("--task", required=True)
    p_dec_add.add_argument("--json")
    p_dec_add.add_argument("--file")
    p_dec_add.set_defaults(func=cmd_decision_add)

    p_dec_list = sp_decision.add_parser("list")
    p_dec_list.add_argument("--task", required=True)
    p_dec_list.add_argument("--status")
    p_dec_list.set_defaults(func=cmd_decision_list)

    p_dec_accept = sp_decision.add_parser("accept")
    p_dec_accept.add_argument("--decision", required=True)
    p_dec_accept.set_defaults(func=cmd_decision_accept)

    p_dec_reject = sp_decision.add_parser("reject")
    p_dec_reject.add_argument("--decision", required=True)
    p_dec_reject.set_defaults(func=cmd_decision_reject)

    # question
    p_question = sub.add_parser("question", help="open question commands")
    sp_question = p_question.add_subparsers(dest="question_command")

    p_q_add = sp_question.add_parser("add")
    p_q_add.add_argument("--task", required=True)
    p_q_add.add_argument("--json")
    p_q_add.add_argument("--file")
    p_q_add.set_defaults(func=cmd_question_add)

    p_q_list = sp_question.add_parser("list")
    p_q_list.add_argument("--task", required=True)
    p_q_list.add_argument("--status")
    p_q_list.add_argument("--priority")
    p_q_list.set_defaults(func=cmd_question_list)

    p_q_answer = sp_question.add_parser("answer")
    p_q_answer.add_argument("--question", required=True)
    p_q_answer.add_argument("--answer", required=True)
    p_q_answer.set_defaults(func=cmd_question_answer)

    p_q_defer = sp_question.add_parser("defer")
    p_q_defer.add_argument("--question", required=True)
    p_q_defer.add_argument("--reason")
    p_q_defer.set_defaults(func=cmd_question_defer)

    # run
    p_run = sub.add_parser("run", help="run commands")
    sp_run = p_run.add_subparsers(dest="run_command")

    p_run_start = sp_run.add_parser("start")
    p_run_start.add_argument("--task", required=True)
    p_run_start.add_argument("--run-type", required=True)
    p_run_start.add_argument("--actor-type", required=True)
    p_run_start.add_argument("--actor-id")
    p_run_start.add_argument("--input-ref")
    p_run_start.set_defaults(func=cmd_run_start)

    p_run_list = sp_run.add_parser("list")
    p_run_list.add_argument("--task", required=True)
    p_run_list.add_argument("--status")
    p_run_list.set_defaults(func=cmd_run_list)

    p_run_finish = sp_run.add_parser("finish")
    p_run_finish.add_argument("--run", required=True)
    p_run_finish.add_argument("--status", required=True)
    p_run_finish.add_argument("--output-ref")
    p_run_finish.set_defaults(func=cmd_run_finish)

    # context
    p_context = sub.add_parser("context", help="context bundle commands")
    sp_context = p_context.add_subparsers(dest="context_command")

    p_ctx_build = sp_context.add_parser("build")
    p_ctx_build.add_argument("--task", required=True)
    p_ctx_build.add_argument("--reason", required=True)
    p_ctx_build.set_defaults(func=cmd_context_build)

    p_ctx_show = sp_context.add_parser("show")
    p_ctx_show.add_argument("--bundle", required=True)
    p_ctx_show.set_defaults(func=cmd_context_show)

    # export
    p_export = sub.add_parser("export", help="export commands")
    sp_export = p_export.add_subparsers(dest="export_command")

    p_export_task = sp_export.add_parser("task")
    p_export_task.add_argument("--task", required=True)
    p_export_task.add_argument("--output", required=True)
    p_export_task.set_defaults(func=cmd_export_task)

    return parser
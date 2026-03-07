#!/usr/bin/env python3
"""
agent-taskstate CLI MVP

Agent-first, SQLite-backed CLI for long-running task state management.

Features:
- SQLite single-file storage
- JSON-only output contract
- Typed refs
- Task / State / Decision / Question / Run / Context Bundle / Export
- Optimistic lock on task_state.patch

This is a single-file MVP intended to be easy to run, inspect, and extend.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

APP_NAME = "agent-taskstate"
DEFAULT_DB_PATH = os.path.join(Path.home(), ".agent-taskstate", "agent-taskstate.db")
ISO = "%Y-%m-%dT%H:%M:%S.%fZ"

TASK_KINDS = {"bugfix", "feature", "research"}
TASK_STATUSES = {
    "draft",
    "ready",
    "in_progress",
    "blocked",
    "review",
    "done",
    "archived",
}
TASK_PRIORITIES = {"low", "medium", "high", "critical"}
OWNER_TYPES = {"human", "agent", "system"}
DECISION_STATUSES = {"proposed", "accepted", "rejected", "superseded"}
QUESTION_STATUSES = {"open", "answered", "deferred", "invalid"}
QUESTION_PRIORITIES = {"low", "medium", "high"}
RUN_TYPES = {"plan", "execute", "review", "summarize", "sync", "manual"}
RUN_STATUSES = {"running", "succeeded", "failed", "cancelled"}
BUILD_REASONS = {"normal", "ambiguity", "review", "high_risk", "recovery"}
CONFIDENCE_LEVELS = {"low", "medium", "high", None}

EXPECTED_OUTPUT_SCHEMA = {
    "summary": "string",
    "proposed_actions": ["string"],
    "decision_candidates": ["string"],
    "question_candidates": ["string"],
    "evidence_needed": ["string"],
}

ALLOWED_TRANSITIONS = {
    "draft": {"ready", "archived"},
    "ready": {"in_progress"},
    "in_progress": {"blocked", "review"},
    "blocked": {"in_progress"},
    "review": {"in_progress", "done"},
    "done": {"archived", "in_progress"},
    "archived": set(),
}


class AgentTaskstateError(Exception):
    code = "validation_error"

    def __init__(self, message: str, *, code: Optional[str] = None) -> None:
        super().__init__(message)
        if code:
            self.code = code


class NotFoundError(AgentTaskstateError):
    code = "not_found"


class ConflictError(AgentTaskstateError):
    code = "conflict"


class InvalidTransitionError(AgentTaskstateError):
    code = "invalid_transition"


class DependencyBlockedError(AgentTaskstateError):
    code = "dependency_blocked"


@dataclass
class AppContext:
    db_path: str


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime(ISO)


def gen_id() -> str:
    return uuid.uuid4().hex


def typed_ref(namespace: str, entity_type: str, entity_id: str) -> str:
    return f"{namespace}:{entity_type}:{entity_id}"


def ensure_parent_dir(path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)


@contextmanager
def connect(db_path: str) -> Iterable[sqlite3.Connection]:
    ensure_parent_dir(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def jdump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def jload(value: Optional[str], default: Any = None) -> Any:
    if value is None:
        return default
    return json.loads(value)


def json_ok(data: Any) -> int:
    print(json.dumps({"ok": True, "data": data, "error": None}, ensure_ascii=False, indent=2))
    return 0


def json_error(code: str, message: str) -> int:
    print(
        json.dumps(
            {"ok": False, "data": None, "error": {"code": code, "message": message}},
            ensure_ascii=False,
            indent=2,
        ),
        file=sys.stdout,
    )
    return 1


def require_in(value: str, allowed: Sequence[str] | set[str], field: str) -> None:
    if value not in allowed:
        raise AgentTaskstateError(f"invalid {field}: {value}; allowed={sorted(allowed)}")


def load_json_arg(value: Optional[str] = None, file_path: Optional[str] = None) -> Any:
    if value and file_path:
        raise AgentTaskstateError("pass either --json or --file, not both")
    if file_path:
        return json.loads(Path(file_path).read_text(encoding="utf-8"))
    if value:
        return json.loads(value)
    raise AgentTaskstateError("missing JSON payload; pass --json or --file")


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS tasks (
  id TEXT PRIMARY KEY,
  parent_task_id TEXT,
  kind TEXT NOT NULL,
  title TEXT NOT NULL,
  goal TEXT NOT NULL,
  status TEXT NOT NULL,
  priority TEXT NOT NULL,
  owner_type TEXT NOT NULL,
  owner_id TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(parent_task_id) REFERENCES tasks(id)
);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_kind ON tasks(kind);
CREATE INDEX IF NOT EXISTS idx_tasks_owner ON tasks(owner_type, owner_id);

CREATE TABLE IF NOT EXISTS task_states (
  task_id TEXT PRIMARY KEY,
  revision INTEGER NOT NULL,
  current_step TEXT NOT NULL,
  constraints_json TEXT NOT NULL,
  done_when_json TEXT NOT NULL,
  current_summary TEXT,
  artifact_refs_json TEXT NOT NULL,
  evidence_refs_json TEXT NOT NULL,
  confidence TEXT,
  context_policy_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS decisions (
  id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL,
  summary TEXT NOT NULL,
  rationale TEXT,
  status TEXT NOT NULL,
  confidence TEXT,
  evidence_refs_json TEXT NOT NULL,
  supersedes_decision_id TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE,
  FOREIGN KEY(supersedes_decision_id) REFERENCES decisions(id)
);
CREATE INDEX IF NOT EXISTS idx_decisions_task ON decisions(task_id);
CREATE INDEX IF NOT EXISTS idx_decisions_task_status ON decisions(task_id, status);

CREATE TABLE IF NOT EXISTS open_questions (
  id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL,
  question TEXT NOT NULL,
  priority TEXT NOT NULL,
  status TEXT NOT NULL,
  answer TEXT,
  evidence_refs_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_open_questions_task ON open_questions(task_id);
CREATE INDEX IF NOT EXISTS idx_open_questions_task_status ON open_questions(task_id, status);

CREATE TABLE IF NOT EXISTS runs (
  id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL,
  actor_type TEXT NOT NULL,
  actor_id TEXT,
  run_type TEXT NOT NULL,
  status TEXT NOT NULL,
  input_ref TEXT,
  output_ref TEXT,
  started_at TEXT NOT NULL,
  ended_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_runs_task ON runs(task_id);

CREATE TABLE IF NOT EXISTS context_bundles (
  id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL,
  build_reason TEXT NOT NULL,
  state_snapshot_json TEXT NOT NULL,
  included_decision_refs_json TEXT NOT NULL,
  included_open_question_refs_json TEXT NOT NULL,
  included_artifact_refs_json TEXT NOT NULL,
  included_evidence_refs_json TEXT NOT NULL,
  expected_output_schema_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  metadata_json TEXT,
  FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_context_bundles_task ON context_bundles(task_id);
"""


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)


# ---------- row conversion ----------


def row_to_task(row: sqlite3.Row) -> Dict[str, Any]:
    return dict(row)


def row_to_task_state(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "task_id": row["task_id"],
        "revision": row["revision"],
        "current_step": row["current_step"],
        "constraints": jload(row["constraints_json"], []),
        "done_when": jload(row["done_when_json"], []),
        "current_summary": row["current_summary"],
        "artifact_refs": jload(row["artifact_refs_json"], []),
        "evidence_refs": jload(row["evidence_refs_json"], []),
        "confidence": row["confidence"],
        "context_policy": jload(row["context_policy_json"], {}),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def row_to_decision(row: sqlite3.Row) -> Dict[str, Any]:
    data = dict(row)
    data["evidence_refs"] = jload(row["evidence_refs_json"], [])
    data["ref"] = typed_ref("agent-taskstate", "decision", row["id"])
    del data["evidence_refs_json"]
    return data


def row_to_question(row: sqlite3.Row) -> Dict[str, Any]:
    data = dict(row)
    data["evidence_refs"] = jload(row["evidence_refs_json"], [])
    data["ref"] = typed_ref("agent-taskstate", "question", row["id"])
    del data["evidence_refs_json"]
    return data


def row_to_run(row: sqlite3.Row) -> Dict[str, Any]:
    data = dict(row)
    data["ref"] = typed_ref("agent-taskstate", "run", row["id"])
    return data


def row_to_bundle(row: sqlite3.Row) -> Dict[str, Any]:
    data = dict(row)
    data["state_snapshot"] = jload(row["state_snapshot_json"], {})
    data["included_decision_refs"] = jload(row["included_decision_refs_json"], [])
    data["included_open_question_refs"] = jload(row["included_open_question_refs_json"], [])
    data["included_artifact_refs"] = jload(row["included_artifact_refs_json"], [])
    data["included_evidence_refs"] = jload(row["included_evidence_refs_json"], [])
    data["expected_output_schema"] = jload(row["expected_output_schema_json"], {})
    data["ref"] = typed_ref("agent-taskstate", "context_bundle", row["id"])
    for key in [
        "state_snapshot_json",
        "included_decision_refs_json",
        "included_open_question_refs_json",
        "included_artifact_refs_json",
        "included_evidence_refs_json",
        "expected_output_schema_json",
    ]:
        del data[key]
    return data


# ---------- fetch helpers ----------


def fetch_one(conn: sqlite3.Connection, sql: str, params: Sequence[Any]) -> sqlite3.Row:
    row = conn.execute(sql, params).fetchone()
    if row is None:
        raise NotFoundError("resource not found")
    return row


def get_task(conn: sqlite3.Connection, task_id: str) -> sqlite3.Row:
    return fetch_one(conn, "SELECT * FROM tasks WHERE id = ?", (task_id,))


def get_task_state(conn: sqlite3.Connection, task_id: str) -> sqlite3.Row:
    return fetch_one(conn, "SELECT * FROM task_states WHERE task_id = ?", (task_id,))


def get_decision(conn: sqlite3.Connection, decision_id: str) -> sqlite3.Row:
    return fetch_one(conn, "SELECT * FROM decisions WHERE id = ?", (decision_id,))


def get_question(conn: sqlite3.Connection, question_id: str) -> sqlite3.Row:
    return fetch_one(conn, "SELECT * FROM open_questions WHERE id = ?", (question_id,))


def get_run(conn: sqlite3.Connection, run_id: str) -> sqlite3.Row:
    return fetch_one(conn, "SELECT * FROM runs WHERE id = ?", (run_id,))


def get_bundle(conn: sqlite3.Connection, bundle_id: str) -> sqlite3.Row:
    return fetch_one(conn, "SELECT * FROM context_bundles WHERE id = ?", (bundle_id,))


# ---------- validation ----------


def validate_task_payload(data: Dict[str, Any]) -> None:
    require_in(data["kind"], TASK_KINDS, "kind")
    require_in(data.get("status", "draft"), TASK_STATUSES, "status")
    require_in(data.get("priority", "medium"), TASK_PRIORITIES, "priority")
    require_in(data.get("owner_type", "human"), OWNER_TYPES, "owner_type")
    if data.get("parent_task_id"):
        if not isinstance(data["parent_task_id"], str):
            raise AgentTaskstateError("parent_task_id must be string")


def validate_state_payload(data: Dict[str, Any]) -> None:
    if not data.get("current_step"):
        raise AgentTaskstateError("current_step is required")
    if not isinstance(data.get("constraints", []), list):
        raise AgentTaskstateError("constraints must be array")
    if not isinstance(data.get("done_when", []), list):
        raise AgentTaskstateError("done_when must be array")
    if not isinstance(data.get("artifact_refs", []), list):
        raise AgentTaskstateError("artifact_refs must be array")
    if not isinstance(data.get("evidence_refs", []), list):
        raise AgentTaskstateError("evidence_refs must be array")
    if not isinstance(data.get("context_policy", {}), dict):
        raise AgentTaskstateError("context_policy must be object")
    require_in(data.get("confidence"), CONFIDENCE_LEVELS, "confidence")


def validate_decision_payload(data: Dict[str, Any]) -> None:
    if not data.get("summary"):
        raise AgentTaskstateError("summary is required")
    require_in(data.get("status", "proposed"), DECISION_STATUSES, "decision.status")
    require_in(data.get("confidence", "medium"), CONFIDENCE_LEVELS, "decision.confidence")
    if not isinstance(data.get("evidence_refs", []), list):
        raise AgentTaskstateError("evidence_refs must be array")


def validate_question_payload(data: Dict[str, Any]) -> None:
    if not data.get("question"):
        raise AgentTaskstateError("question is required")
    require_in(data.get("priority", "medium"), QUESTION_PRIORITIES, "question.priority")
    require_in(data.get("status", "open"), QUESTION_STATUSES, "question.status")
    if not isinstance(data.get("evidence_refs", []), list):
        raise AgentTaskstateError("evidence_refs must be array")


# ---------- guards ----------


def count_open_high_questions(conn: sqlite3.Connection, task_id: str) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS c FROM open_questions WHERE task_id = ? AND status = 'open' AND priority = 'high'",
        (task_id,),
    ).fetchone()
    return int(row["c"])


def count_relevant_decisions(conn: sqlite3.Connection, task_id: str) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS c FROM decisions WHERE task_id = ? AND status IN ('accepted', 'proposed')",
        (task_id,),
    ).fetchone()
    return int(row["c"])


def is_done_when_satisfied(done_when: List[Any]) -> bool:
    if not done_when:
        return False
    for item in done_when:
        if isinstance(item, dict):
            if not bool(item.get("done", False)):
                return False
        else:
            return False
    return True


def validate_status_transition(conn: sqlite3.Connection, task_row: sqlite3.Row, to_status: str) -> None:
    require_in(to_status, TASK_STATUSES, "status")
    from_status = task_row["status"]
    if to_status not in ALLOWED_TRANSITIONS.get(from_status, set()):
        raise InvalidTransitionError(f"transition not allowed: {from_status} -> {to_status}")

    task = row_to_task(task_row)
    state: Optional[Dict[str, Any]] = None
    try:
        state = row_to_task_state(get_task_state(conn, task_row["id"]))
    except NotFoundError:
        state = None

    if to_status == "ready":
        if not task["goal"]:
            raise DependencyBlockedError("goal must be set before moving to ready")
        if not state or not state["done_when"]:
            raise DependencyBlockedError("done_when must contain at least one item before moving to ready")
        if not task["kind"]:
            raise DependencyBlockedError("kind must be set before moving to ready")

    if to_status == "in_progress":
        if not state:
            raise DependencyBlockedError("task_state must exist before moving to in_progress")
        if not state["current_step"]:
            raise DependencyBlockedError("current_step must be set before moving to in_progress")

    if to_status == "review":
        if count_open_high_questions(conn, task_row["id"]) > 0:
            raise DependencyBlockedError("high priority open questions must be 0 before moving to review")
        if count_relevant_decisions(conn, task_row["id"]) == 0:
            raise DependencyBlockedError("at least one accepted/proposed decision is required before moving to review")

    if to_status == "done":
        if from_status != "review":
            raise InvalidTransitionError("done is only allowed from review")
        if not state:
            raise DependencyBlockedError("task_state must exist before moving to done")
        if not is_done_when_satisfied(state["done_when"]):
            raise DependencyBlockedError("all done_when items must be satisfied before moving to done")
        if not state.get("current_summary"):
            raise DependencyBlockedError("current_summary must be set before moving to done")


# ---------- task ----------


def cmd_init(ctx: AppContext, _args: argparse.Namespace) -> int:
    with connect(ctx.db_path) as conn:
        init_db(conn)
    return json_ok({"db_path": ctx.db_path, "initialized": True})


def cmd_task_create(ctx: AppContext, args: argparse.Namespace) -> int:
    payload = load_json_arg(args.json, args.file)
    validate_task_payload(payload)
    task_id = payload.get("id") or gen_id()
    now = now_utc()
    with connect(ctx.db_path) as conn:
        init_db(conn)
        if payload.get("parent_task_id"):
            get_task(conn, payload["parent_task_id"])
        conn.execute(
            """
            INSERT INTO tasks (id, parent_task_id, kind, title, goal, status, priority, owner_type, owner_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                now,
                now,
            ),
        )
        row = get_task(conn, task_id)
    return json_ok({**row_to_task(row), "ref": typed_ref("agent-taskstate", "task", task_id)})


def cmd_task_show(ctx: AppContext, args: argparse.Namespace) -> int:
    with connect(ctx.db_path) as conn:
        row = get_task(conn, args.task)
        data = row_to_task(row)
        data["ref"] = typed_ref("agent-taskstate", "task", args.task)
        try:
            data["state"] = row_to_task_state(get_task_state(conn, args.task))
        except NotFoundError:
            data["state"] = None
    return json_ok(data)


def cmd_task_list(ctx: AppContext, args: argparse.Namespace) -> int:
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
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"SELECT * FROM tasks {where} ORDER BY updated_at DESC, created_at DESC"
    with connect(ctx.db_path) as conn:
        rows = conn.execute(sql, params).fetchall()
    data = [{**row_to_task(r), "ref": typed_ref("agent-taskstate", "task", r["id"])} for r in rows]
    return json_ok(data)


def cmd_task_update(ctx: AppContext, args: argparse.Namespace) -> int:
    payload = load_json_arg(args.json, args.file)
    allowed = {"parent_task_id", "kind", "title", "goal", "priority", "owner_type", "owner_id"}
    updates = {k: v for k, v in payload.items() if k in allowed}
    if not updates:
        raise AgentTaskstateError("no updatable fields provided")
    if "kind" in updates:
        require_in(updates["kind"], TASK_KINDS, "kind")
    if "priority" in updates:
        require_in(updates["priority"], TASK_PRIORITIES, "priority")
    if "owner_type" in updates:
        require_in(updates["owner_type"], OWNER_TYPES, "owner_type")
    with connect(ctx.db_path) as conn:
        init_db(conn)
        get_task(conn, args.task)
        if updates.get("parent_task_id"):
            get_task(conn, updates["parent_task_id"])
        updates["updated_at"] = now_utc()
        fields = ", ".join([f"{k} = ?" for k in updates])
        conn.execute(f"UPDATE tasks SET {fields} WHERE id = ?", [*updates.values(), args.task])
        row = get_task(conn, args.task)
    return json_ok({**row_to_task(row), "ref": typed_ref("agent-taskstate", "task", args.task)})


def cmd_task_set_status(ctx: AppContext, args: argparse.Namespace) -> int:
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
    data = {**row_to_task(row), "ref": typed_ref("agent-taskstate", "task", args.task)}
    if args.reason:
        data["transition_reason"] = args.reason
    return json_ok(data)


# ---------- state ----------


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
    return normalized


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
        existing = conn.execute("SELECT revision FROM task_states WHERE task_id = ?", (args.task,)).fetchone()
        if existing is None:
            revision = 1
            conn.execute(
                """
                INSERT INTO task_states (
                    task_id, revision, current_step, constraints_json, done_when_json, current_summary,
                    artifact_refs_json, evidence_refs_json, confidence, context_policy_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    args.task,
                    revision,
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
        else:
            revision = int(existing["revision"]) + 1
            conn.execute(
                """
                UPDATE task_states
                   SET revision = ?, current_step = ?, constraints_json = ?, done_when_json = ?, current_summary = ?,
                       artifact_refs_json = ?, evidence_refs_json = ?, confidence = ?, context_policy_json = ?, updated_at = ?
                 WHERE task_id = ?
                """,
                (
                    revision,
                    payload["current_step"],
                    jdump(payload["constraints"]),
                    jdump(payload["done_when"]),
                    payload["current_summary"],
                    jdump(payload["artifact_refs"]),
                    jdump(payload["evidence_refs"]),
                    payload["confidence"],
                    jdump(payload["context_policy"]),
                    now,
                    args.task,
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
        row = get_task_state(conn, args.task)
        state = row_to_task_state(row)
        if int(state["revision"]) != int(args.expected_revision):
            raise ConflictError("revision mismatch")
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
        revision = int(state["revision"]) + 1
        conn.execute(
            """
            UPDATE task_states
               SET revision = ?, current_step = ?, constraints_json = ?, done_when_json = ?, current_summary = ?,
                   artifact_refs_json = ?, evidence_refs_json = ?, confidence = ?, context_policy_json = ?, updated_at = ?
             WHERE task_id = ?
            """,
            (
                revision,
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
            ),
        )
        conn.execute("UPDATE tasks SET updated_at = ? WHERE id = ?", (now, args.task))
        row = get_task_state(conn, args.task)
    return json_ok(row_to_task_state(row))


# ---------- decision ----------


def cmd_decision_add(ctx: AppContext, args: argparse.Namespace) -> int:
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
    require_in(status, DECISION_STATUSES, "decision.status")
    with connect(ctx.db_path) as conn:
        init_db(conn)
        row = get_decision(conn, decision_id)
        conn.execute(
            "UPDATE decisions SET status = ?, updated_at = ? WHERE id = ?",
            (status, now_utc(), decision_id),
        )
        row = get_decision(conn, decision_id)
    return json_ok(row_to_decision(row))


def cmd_decision_accept(ctx: AppContext, args: argparse.Namespace) -> int:
    return _set_decision_status(ctx, args.decision, "accepted")


def cmd_decision_reject(ctx: AppContext, args: argparse.Namespace) -> int:
    return _set_decision_status(ctx, args.decision, "rejected")


# ---------- question ----------


def cmd_question_add(ctx: AppContext, args: argparse.Namespace) -> int:
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


# ---------- run ----------


def cmd_run_start(ctx: AppContext, args: argparse.Namespace) -> int:
    require_in(args.run_type, RUN_TYPES, "run_type")
    require_in(args.actor_type, OWNER_TYPES, "actor_type")
    now = now_utc()
    rid = gen_id()
    with connect(ctx.db_path) as conn:
        init_db(conn)
        get_task(conn, args.task)
        conn.execute(
            """
            INSERT INTO runs (
              id, task_id, actor_type, actor_id, run_type, status, input_ref, output_ref, started_at, ended_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 'running', ?, NULL, ?, NULL, ?, ?)
            """,
            (rid, args.task, args.actor_type, args.actor_id, args.run_type, args.input_ref, now, now, now),
        )
        row = get_run(conn, rid)
    return json_ok(row_to_run(row))


def cmd_run_finish(ctx: AppContext, args: argparse.Namespace) -> int:
    require_in(args.status, RUN_STATUSES - {"running"}, "run.status")
    now = now_utc()
    with connect(ctx.db_path) as conn:
        init_db(conn)
        row = get_run(conn, args.run)
        if row["status"] != "running":
            raise ConflictError("run is not in running state")
        conn.execute(
            "UPDATE runs SET status = ?, output_ref = ?, ended_at = ?, updated_at = ? WHERE id = ?",
            (args.status, args.output_ref, now, now, args.run),
        )
        row = get_run(conn, args.run)
    return json_ok(row_to_run(row))


# ---------- context ----------


def should_include_evidence(state: Dict[str, Any], build_reason: str, decisions: List[Dict[str, Any]], questions: List[Dict[str, Any]]) -> bool:
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
            "task_ref": typed_ref("agent-taskstate", "task", task["id"]),
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
    with connect(ctx.db_path) as conn:
        row = get_bundle(conn, args.bundle)
    return json_ok(row_to_bundle(row))


# ---------- export ----------


def cmd_export_task(ctx: AppContext, args: argparse.Namespace) -> int:
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
        "task": {**task, "ref": typed_ref("agent-taskstate", "task", task["id"])} ,
        "task_state": state,
        "decisions": decisions,
        "open_questions": questions,
        "runs": runs,
        "context_bundles": bundles,
        "exported_at": now_utc(),
    }
    Path(args.output).write_text(json.dumps(export, ensure_ascii=False, indent=2), encoding="utf-8")
    return json_ok({"task": args.task, "output": args.output})


# ---------- parser ----------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=APP_NAME, description="agent-taskstate CLI MVP")
    parser.add_argument("--db", default=os.environ.get("AGENT_TASKSTATE_DB", DEFAULT_DB_PATH), help="SQLite DB path")

    sub = parser.add_subparsers(dest="command")

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


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 2
    ctx = AppContext(db_path=args.db)
    try:
        return int(args.func(ctx, args))
    except AgentTaskstateError as e:
        return json_error(e.code, str(e))
    except sqlite3.IntegrityError as e:
        return json_error("validation_error", f"sqlite integrity error: {e}")
    except json.JSONDecodeError as e:
        return json_error("validation_error", f"invalid JSON: {e}")
    except Exception as e:
        return json_error("validation_error", f"unexpected error: {e}")


if __name__ == "__main__":
    raise SystemExit(main())

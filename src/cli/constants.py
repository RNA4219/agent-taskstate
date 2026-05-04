"""
CLI Constants and Type Definitions
"""

from __future__ import annotations

import os
from pathlib import Path

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
REPLY_STATES = {"pending", "sent", "failed", "skipped"}

TASK_PHASE2_COLUMNS = {
    "idempotency_key": "TEXT",
    "note_id": "TEXT",
    "trace_id": "TEXT",
    "reply_target": "TEXT",
    "reply_state": "TEXT",
    "retry_count": "INTEGER NOT NULL DEFAULT 0",
    "kestra_execution_id": "TEXT",
    "original_task_id": "TEXT",
    "trigger": "TEXT",
    "reply_text": "TEXT",
    "roadmap_request_json": "TEXT",
}

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
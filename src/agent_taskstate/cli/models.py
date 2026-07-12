"""CLI row conversion helpers."""

from __future__ import annotations

import json
import sqlite3
from typing import Any, Dict, Optional

from .typed_ref import typed_ref


def jdump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def jload(value: Optional[str], default: Any = None) -> Any:
    if value is None:
        return default
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return default


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
    data["evidence_refs"] = jload(data.pop("evidence_refs_json", None), [])
    data["ref"] = typed_ref("agent-taskstate", "decision", row["id"])
    return data


def row_to_question(row: sqlite3.Row) -> Dict[str, Any]:
    data = dict(row)
    data["evidence_refs"] = jload(data.pop("evidence_refs_json", None), [])
    data["ref"] = typed_ref("agent-taskstate", "question", row["id"])
    return data


def row_to_run(row: sqlite3.Row) -> Dict[str, Any]:
    data = dict(row)
    data["ref"] = typed_ref("agent-taskstate", "run", row["id"])
    return data


def row_to_bundle(row: sqlite3.Row) -> Dict[str, Any]:
    data = dict(row)
    json_columns = {
        "state_snapshot": "state_snapshot_json",
        "included_decision_refs": "included_decision_refs_json",
        "included_open_question_refs": "included_open_question_refs_json",
        "included_artifact_refs": "included_artifact_refs_json",
        "included_evidence_refs": "included_evidence_refs_json",
        "expected_output_schema": "expected_output_schema_json",
        "decision_digest": "decision_digest_json",
        "question_digest": "question_digest_json",
        "diagnostics": "diagnostics_json",
    }
    for output, column in json_columns.items():
        if column in data:
            data[output] = jload(
                data.pop(column),
                None if output in {"decision_digest", "question_digest", "diagnostics"} else {},
            )
    data["raw_included"] = bool(data["raw_included"]) if "raw_included" in data else False
    data["ref"] = typed_ref("agent-taskstate", "context_bundle", row["id"])
    return data

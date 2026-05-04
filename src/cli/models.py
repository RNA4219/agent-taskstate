"""
CLI Models and Row Conversion
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any, Dict, Optional

from .typed_ref import typed_ref


def jdump(value: Any) -> str:
    """Dump value to JSON string."""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def jload(value: Optional[str], default: Any = None) -> Any:
    """Load JSON string to value."""
    if value is None:
        return default
    return json.loads(value)


def row_to_task(row: sqlite3.Row) -> Dict[str, Any]:
    """Convert task row to dict."""
    return dict(row)


def row_to_task_state(row: sqlite3.Row) -> Dict[str, Any]:
    """Convert task_state row to dict."""
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
    """Convert decision row to dict."""
    data = dict(row)
    data["evidence_refs"] = jload(row["evidence_refs_json"], [])
    data["ref"] = typed_ref("agent-taskstate", "decision", row["id"])
    del data["evidence_refs_json"]
    return data


def row_to_question(row: sqlite3.Row) -> Dict[str, Any]:
    """Convert question row to dict."""
    data = dict(row)
    data["evidence_refs"] = jload(row["evidence_refs_json"], [])
    data["ref"] = typed_ref("agent-taskstate", "question", row["id"])
    del data["evidence_refs_json"]
    return data


def row_to_run(row: sqlite3.Row) -> Dict[str, Any]:
    """Convert run row to dict."""
    data = dict(row)
    data["ref"] = typed_ref("agent-taskstate", "run", row["id"])
    return data


def row_to_bundle(row: sqlite3.Row) -> Dict[str, Any]:
    """Convert context_bundle row to dict."""
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
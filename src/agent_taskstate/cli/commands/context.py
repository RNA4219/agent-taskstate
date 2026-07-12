"""Context rebuild CLI commands."""

from __future__ import annotations

import argparse
import json

from ...context_bundle import ContextRebuildService
from .. import AppContext
from ..constants import BUILD_REASONS
from ..db import connect, init_db
from ..errors import AgentTaskstateError
from ..fetch import get_bundle
from ..models import row_to_bundle
from ..utils import json_ok
from ..validation import require_in


def should_include_evidence(state, build_reason, decisions, questions) -> bool:
    return (
        state.get("confidence") == "low"
        or build_reason in {"review", "high_risk"}
        or state.get("current_step") in {"investigation", "verification"}
        or state.get("context_policy", {}).get("force_evidence") is True
        or any(item.get("confidence") == "low" for item in decisions)
        or any(
            item.get("priority") == "high" and item.get("status") == "open" for item in questions
        )
    )


def cmd_context_build(ctx: AppContext, args: argparse.Namespace) -> int:
    reason = getattr(args, "reason", "normal")
    require_in(reason, BUILD_REASONS, "build_reason")
    purpose = getattr(args, "purpose", "continue_work")
    rebuild_level = getattr(args, "rebuild_level", "L2")
    include_raw = bool(getattr(args, "include_raw", False))
    with connect(ctx.db_path) as conn:
        init_db(conn)
        try:
            bundle = ContextRebuildService(conn).build(
                args.task,
                purpose=purpose,
                rebuild_level=rebuild_level,
                include_raw=include_raw,
                reason=reason,
            )
        except ValueError as exc:
            code = "not_found" if str(exc).startswith("Task not found") else "validation_error"
            raise AgentTaskstateError(str(exc), code=code) from exc
        data = bundle.to_dict()
        data["build_reason"] = reason
        data["included_decision_refs"] = [
            item["ref"] for item in json.loads(bundle.decision_digest_json or "{}").get("items", [])
        ]
        data["included_open_question_refs"] = [
            item["ref"] for item in json.loads(bundle.question_digest_json or "{}").get("items", [])
        ]
        data["included_artifact_refs"] = [
            source.typed_ref for source in bundle.sources if source.source_kind == "artifact"
        ]
        data["included_evidence_refs"] = [
            source.typed_ref for source in bundle.sources if source.source_kind == "evidence"
        ]
    return json_ok(data)


def cmd_context_show(ctx: AppContext, args: argparse.Namespace) -> int:
    with connect(ctx.db_path) as conn:
        init_db(conn)
        row = get_bundle(conn, args.bundle)
        data = row_to_bundle(row)
        sources = conn.execute(
            """
            SELECT id, context_bundle_id, typed_ref, source_kind, selected_raw, metadata_json, created_at
            FROM context_bundle_sources
            WHERE context_bundle_id = ?
            ORDER BY created_at ASC, id ASC
            """,
            (args.bundle,),
        ).fetchall()
        data["sources"] = [
            {
                "id": source["id"],
                "context_bundle_id": source["context_bundle_id"],
                "typed_ref": source["typed_ref"],
                "source_kind": source["source_kind"],
                "selected_raw": bool(source["selected_raw"]),
                "metadata": json.loads(source["metadata_json"])
                if source["metadata_json"]
                else None,
                "created_at": source["created_at"],
            }
            for source in sources
        ]
        data["source_refs"] = [source["typed_ref"] for source in sources]
    return json_ok(data)

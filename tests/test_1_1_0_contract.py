"""1.1.0 integration contract tests."""

from __future__ import annotations

import importlib
import json
import sqlite3
import warnings

import pytest

from agent_taskstate.cli import AppContext
from agent_taskstate.cli.commands import (
    cmd_context_build,
    cmd_state_patch,
    cmd_state_put,
    cmd_task_create,
    cmd_task_history,
    cmd_task_set_status,
)
from agent_taskstate.cli.db import init_db
from agent_taskstate.tracker_bridge import TrackerBridgeService
from .helpers import create_task, capture_output


def test_legacy_plural_migration_backfills_once(tmp_path):
    path = tmp_path / "legacy.db"
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE tasks (
          id TEXT PRIMARY KEY, kind TEXT, title TEXT, goal TEXT, status TEXT,
          priority TEXT, owner_type TEXT, owner_id TEXT, created_at TEXT, updated_at TEXT
        );
        CREATE TABLE context_bundles (
          id TEXT PRIMARY KEY, task_id TEXT, build_reason TEXT, state_snapshot_json TEXT,
          included_decision_refs_json TEXT, included_open_question_refs_json TEXT,
          included_artifact_refs_json TEXT, included_evidence_refs_json TEXT,
          expected_output_schema_json TEXT, created_at TEXT
        );
        INSERT INTO tasks VALUES
          ('task-legacy','feature','Legacy','Goal','draft','medium','system',NULL,'2026-01-01','2026-01-01');
        INSERT INTO context_bundles VALUES
          ('bundle-legacy','task-legacy','normal','{}','[]','[]',
           '["memx:evidence:ev-1"]','[]','{}','2026-01-01');
        """
    )
    conn.commit()
    init_db(conn)
    first = conn.execute("SELECT COUNT(*) FROM state_transitions").fetchone()[0]
    sources = conn.execute("SELECT typed_ref FROM context_bundle_sources").fetchall()
    assert first == 1
    assert sources[0][0] == "memx:evidence:local:ev-1"
    bundle = conn.execute(
        "SELECT rebuild_level, generator_version, diagnostics_json FROM context_bundles"
    ).fetchone()
    assert tuple(bundle) == ("L1", "legacy/1.0.1", '{"legacy_backfill": true}')
    init_db(conn)
    assert conn.execute("SELECT COUNT(*) FROM state_transitions").fetchone()[0] == first
    conn.close()


def test_status_history_and_noop(tmp_path):
    ctx = AppContext(str(tmp_path / "state.db"))
    created = json.loads(_capture(cmd_task_create, ctx, {"kind": "feature", "title": "T", "goal": "G"}))
    task_id = created["data"]["id"]
    initial = {"current_step": "start", "done_when": ["ready"], "constraints": [], "artifact_refs": [], "evidence_refs": [], "confidence": "medium", "context_policy": {}}
    assert json.loads(_capture(cmd_state_put, ctx, {"task": task_id, "json": json.dumps(initial), "file": None}))["ok"]
    assert json.loads(_capture(cmd_task_set_status, ctx, {"task": task_id, "to": "ready", "reason": None, "actor_type": "system", "actor_id": None, "run": None, "reason_required": False}))["ok"]
    noop = json.loads(_capture(cmd_task_set_status, ctx, {"task": task_id, "to": "ready", "reason": None, "actor_type": "system", "actor_id": None, "run": None, "reason_required": False}))
    assert noop["data"]["no_op"] is True
    history = json.loads(_capture(cmd_task_history, ctx, {"task": task_id}))
    assert len(history["data"]) == 2
    assert history["data"][0]["from_status"] is None
    assert history["data"][1]["to_status"] == "ready"


def test_state_patch_is_revision_guarded(tmp_path):
    ctx = AppContext(str(tmp_path / "state.db"))
    created = json.loads(_capture(cmd_task_create, ctx, {"kind": "feature", "title": "T", "goal": "G"}))
    task_id = created["data"]["id"]
    initial = {"current_step": "start", "done_when": [], "constraints": [], "artifact_refs": [], "evidence_refs": [], "confidence": "medium", "context_policy": {}}
    assert json.loads(_capture(cmd_state_put, ctx, {"task": task_id, "json": json.dumps(initial), "file": None}))["ok"]
    patch = json.dumps({"current_step": "one"})
    assert json.loads(_capture(cmd_state_patch, ctx, {"task": task_id, "expected_revision": 1, "json": patch, "file": None}))["ok"]
    conflict = json.loads(_capture(cmd_state_patch, ctx, {"task": task_id, "expected_revision": 1, "json": patch, "file": None}))
    assert conflict["error"]["code"] == "conflict"


def test_context_build_keeps_unsupported_diagnostics(tmp_path):
    ctx = AppContext(str(tmp_path / "context.db"))
    created = json.loads(_capture(cmd_task_create, ctx, {"kind": "feature", "title": "T", "goal": "G"}))
    task_id = created["data"]["id"]
    state = {"current_step": "investigation", "done_when": [], "constraints": [], "artifact_refs": [], "evidence_refs": ["memx:evidence:missing"], "confidence": "low", "context_policy": {}}
    assert json.loads(_capture(cmd_state_put, ctx, {"task": task_id, "json": json.dumps(state), "file": None}))["ok"]
    result = json.loads(_capture(cmd_context_build, ctx, {"task": task_id, "reason": "review", "purpose": "review_prepare", "rebuild_level": "L2", "include_raw": True}))
    assert result["ok"]
    assert result["data"]["diagnostics"]["unsupported_refs"] == ["memx:evidence:local:missing"]
    assert result["data"]["raw_included"] is True


def test_tracker_secret_values_are_rejected(tmp_path):
    conn = sqlite3.connect(tmp_path / "tracker.db")
    init_db(conn)
    service = TrackerBridgeService(conn)
    with pytest.raises(ValueError, match="secret"):
        service.create_connection("github", "bad", {"token": "plain"})
    item = service.create_connection("github", "good", {"url": "https://example.invalid"}, {"token": "GITHUB_TOKEN"})
    assert "plain" not in item.config_json
    assert json.loads(item.secret_env_json)["token"] == "GITHUB_TOKEN"



def test_cli_compat_shim_warns():
    import sys

    sys.modules.pop("cli", None)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        module = importlib.import_module("cli")
    assert module.main is not None
    assert any(item.category is DeprecationWarning for item in caught)

def _capture(func, ctx, values):
    values = {"json": None, "file": None, **values}
    if func is cmd_task_create and values["json"] is None:
        values["json"] = json.dumps({key: value for key, value in values.items() if key not in {"json", "file"}})

    return json.dumps(capture_output(func, ctx, type("Args", (), values)()))

"""
Test cases for Task State Management.

Corresponds to: docs/tests/state.feature
Spec reference: MVP Spec 5.2, 12
"""

import json

import pytest

from .helpers import workx, create_task, create_task_state, cmd_state_put, cmd_state_get, cmd_state_patch


class TestStatePut:
    """Test state put command."""

    def test_create_new_task_state(self, empty_db):
        """Spec 5.2: Create new task state."""
        ctx = workx.AppContext(db_path=empty_db)

        with workx.connect(empty_db) as conn:
            task_id = create_task(conn)

        state_data = {
            "current_step": "実装中",
            "constraints": ["制約1", "制約2"],
            "done_when": ["条件1", "条件2"],
            "current_summary": "現在の要約",
            "artifact_refs": [],
            "evidence_refs": [],
            "confidence": "medium",
            "context_policy": {"force_evidence": False},
        }

        output = cmd_state_put(ctx, task_id=task_id, state_json=state_data)

        assert output["ok"] is True
        with workx.connect(empty_db) as conn:
            row = conn.execute(
                "SELECT * FROM task_states WHERE task_id = ?", (task_id,)
            ).fetchone()
            assert row is not None
            assert row["revision"] == 1
            assert row["current_step"] == "実装中"

    def test_state_put_overwrites_existing(self, empty_db):
        """State put updates existing state and increments revision."""
        ctx = workx.AppContext(db_path=empty_db)

        with workx.connect(empty_db) as conn:
            task_id = create_task(conn)
            create_task_state(conn, task_id, revision=5, current_step="古い状態")

        state_data = {
            "current_step": "新しい状態",
            "constraints": [],
            "done_when": ["条件1"],
            "current_summary": "",
            "artifact_refs": [],
            "evidence_refs": [],
            "confidence": "high",
            "context_policy": {},
        }

        output = cmd_state_put(ctx, task_id=task_id, state_json=state_data)

        assert output["ok"] is True
        with workx.connect(empty_db) as conn:
            row = conn.execute(
                "SELECT revision, current_step FROM task_states WHERE task_id = ?", (task_id,)
            ).fetchone()
            assert row["revision"] == 6  # 5 + 1 = incremented revision
            assert row["current_step"] == "新しい状態"


class TestStateGet:
    """Test state get command."""

    def test_get_existing_task_state(self, empty_db):
        """Spec 5.2: Get existing task state."""
        ctx = workx.AppContext(db_path=empty_db)

        with workx.connect(empty_db) as conn:
            task_id = create_task(conn)
            create_task_state(conn, task_id, revision=3, current_step="レビュー中", confidence="high")

        output = cmd_state_get(ctx, task_id=task_id)

        assert output["ok"] is True
        assert output["data"]["revision"] == 3
        assert output["data"]["current_step"] == "レビュー中"

    def test_get_nonexistent_state_returns_not_found(self, empty_db):
        """Get state for task without state returns not_found."""
        ctx = workx.AppContext(db_path=empty_db)

        with workx.connect(empty_db) as conn:
            task_id = create_task(conn)

        output = cmd_state_get(ctx, task_id=task_id)

        assert output["ok"] is False
        assert output["error"]["code"] == "not_found"


class TestStatePatch:
    """Test state patch command with optimistic locking."""

    def test_patch_with_matching_revision(self, empty_db):
        """Spec 12: Patch succeeds when revision matches."""
        ctx = workx.AppContext(db_path=empty_db)

        with workx.connect(empty_db) as conn:
            task_id = create_task(conn)
            create_task_state(conn, task_id, revision=1, current_step="実装前")

        patch_data = {"current_step": "実装中"}

        output = cmd_state_patch(ctx, task_id=task_id, expected_revision=1, patch_json=patch_data)

        assert output["ok"] is True
        with workx.connect(empty_db) as conn:
            row = conn.execute(
                "SELECT revision, current_step FROM task_states WHERE task_id = ?", (task_id,)
            ).fetchone()
            assert row["revision"] == 2
            assert row["current_step"] == "実装中"

    def test_patch_with_mismatched_revision_returns_conflict(self, empty_db):
        """Spec 12: Patch fails with conflict when revision mismatches."""
        ctx = workx.AppContext(db_path=empty_db)

        with workx.connect(empty_db) as conn:
            task_id = create_task(conn)
            create_task_state(conn, task_id, revision=5, current_step="最新状態")

        patch_data = {"current_step": "古い情報で更新"}

        output = cmd_state_patch(ctx, task_id=task_id, expected_revision=3, patch_json=patch_data)

        assert output["ok"] is False
        assert output["error"]["code"] == "conflict"

        # Verify state was not updated
        with workx.connect(empty_db) as conn:
            row = conn.execute(
                "SELECT revision, current_step FROM task_states WHERE task_id = ?", (task_id,)
            ).fetchone()
            assert row["revision"] == 5

    def test_patch_nonexistent_state_returns_not_found(self, empty_db):
        """Patch on task without state returns not_found."""
        ctx = workx.AppContext(db_path=empty_db)

        with workx.connect(empty_db) as conn:
            task_id = create_task(conn)

        patch_data = {"current_step": "test"}

        output = cmd_state_patch(ctx, task_id=task_id, expected_revision=1, patch_json=patch_data)

        assert output["ok"] is False
        assert output["error"]["code"] == "not_found"


class TestStateValidation:
    """Test validation for state operations."""

    @pytest.mark.parametrize("confidence", ["low", "medium", "high"])
    def test_create_with_each_confidence(self, empty_db, confidence):
        """Create state with each valid confidence level."""
        ctx = workx.AppContext(db_path=empty_db)

        with workx.connect(empty_db) as conn:
            task_id = create_task(conn)

        state_data = {
            "current_step": "test",
            "constraints": [],
            "done_when": [],
            "confidence": confidence,
            "context_policy": {},
        }

        output = cmd_state_put(ctx, task_id=task_id, state_json=state_data)

        assert output["ok"] is True


class TestStateConcurrency:
    """Test concurrent update scenarios."""

    def test_concurrent_update_conflict(self, empty_db):
        """Spec 12: Second update fails with conflict."""
        ctx = workx.AppContext(db_path=empty_db)

        with workx.connect(empty_db) as conn:
            task_id = create_task(conn)
            create_task_state(conn, task_id, revision=1)

        # First update succeeds
        output1 = cmd_state_patch(
            ctx, task_id=task_id, expected_revision=1, patch_json={"current_step": "update1"}
        )
        assert output1["ok"] is True

        # Second update with old revision fails
        output2 = cmd_state_patch(
            ctx, task_id=task_id, expected_revision=1, patch_json={"current_step": "update2"}
        )
        assert output2["ok"] is False
        assert output2["error"]["code"] == "conflict"

        # Verify final state
        with workx.connect(empty_db) as conn:
            row = conn.execute(
                "SELECT revision, current_step FROM task_states WHERE task_id = ?", (task_id,)
            ).fetchone()
            assert row["revision"] == 2
            assert row["current_step"] == "update1"
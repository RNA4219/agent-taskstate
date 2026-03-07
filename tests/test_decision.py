"""
Test cases for Decision Management.

Corresponds to: docs/tests/decision.feature
Spec reference: MVP Spec 5.3
"""

import json

import pytest

from .helpers import agent_taskstate, create_task, create_decision, cmd_decision_add, cmd_decision_list, cmd_decision_accept, cmd_decision_reject


class TestDecisionAdd:
    """Test decision add command."""

    def test_add_decision(self, empty_db):
        """Spec 5.3: Add a new decision."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        with agent_taskstate.connect(empty_db) as conn:
            task_id = create_task(conn)

        decision_data = {
            "summary": "DB に SQLite を採用",
            "rationale": "ローカル実行で軽量なため",
            "confidence": "high",
            "evidence_refs": ["memx:evidence:01HEV001"],
        }

        output = cmd_decision_add(ctx, task_id=task_id, decision_json=decision_data)

        assert output["ok"] is True
        assert "id" in output["data"]

        with agent_taskstate.connect(empty_db) as conn:
            row = conn.execute(
                "SELECT * FROM decisions WHERE id = ?", (output["data"]["id"],)
            ).fetchone()
            assert row["status"] == "proposed"
            assert row["confidence"] == "high"

    def test_add_decision_minimal_fields(self, empty_db):
        """Add decision with minimal required fields."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        with agent_taskstate.connect(empty_db) as conn:
            task_id = create_task(conn)

        decision_data = {
            "summary": "シンプルな決定",
            "confidence": "medium",
        }

        output = cmd_decision_add(ctx, task_id=task_id, decision_json=decision_data)

        assert output["ok"] is True

    def test_add_decision_nonexistent_task_returns_not_found(self, empty_db):
        """Add decision to nonexistent task returns not_found."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        decision_data = {"summary": "test", "confidence": "high"}

        output = cmd_decision_add(ctx, task_id="01HNOTFOUND001", decision_json=decision_data)

        assert output["ok"] is False
        assert output["error"]["code"] == "not_found"

    @pytest.mark.parametrize("confidence", ["low", "medium", "high"])
    def test_add_decision_each_confidence(self, empty_db, confidence):
        """Add decision with each valid confidence."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        with agent_taskstate.connect(empty_db) as conn:
            task_id = create_task(conn)

        decision_data = {"summary": "test decision", "confidence": confidence}

        output = cmd_decision_add(ctx, task_id=task_id, decision_json=decision_data)
        assert output["ok"] is True


class TestDecisionList:
    """Test decision list command."""

    def test_list_decisions(self, empty_db):
        """List all decisions for a task."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        with agent_taskstate.connect(empty_db) as conn:
            task_id = create_task(conn)
            create_decision(conn, task_id, summary="Decision 1", status="accepted")
            create_decision(conn, task_id, summary="Decision 2", status="proposed")

        output = cmd_decision_list(ctx, task_id=task_id)

        assert output["ok"] is True
        assert len(output["data"]) == 2

    def test_list_decisions_filter_by_status(self, empty_db):
        """Filter decisions by status."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        with agent_taskstate.connect(empty_db) as conn:
            task_id = create_task(conn)
            create_decision(conn, task_id, status="accepted")
            create_decision(conn, task_id, status="proposed")

        output = cmd_decision_list(ctx, task_id=task_id, status="accepted")

        assert output["ok"] is True
        assert len(output["data"]) == 1
        assert output["data"][0]["status"] == "accepted"


class TestDecisionAccept:
    """Test decision accept command."""

    def test_accept_decision(self, empty_db):
        """Accept a proposed decision."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        with agent_taskstate.connect(empty_db) as conn:
            task_id = create_task(conn)
            decision_id = create_decision(conn, task_id, status="proposed")

        output = cmd_decision_accept(ctx, decision_id=decision_id)

        assert output["ok"] is True
        with agent_taskstate.connect(empty_db) as conn:
            row = conn.execute(
                "SELECT status FROM decisions WHERE id = ?", (decision_id,)
            ).fetchone()
            assert row["status"] == "accepted"

    def test_accept_nonexistent_decision_returns_not_found(self, empty_db):
        """Accept nonexistent decision returns not_found."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        output = cmd_decision_accept(ctx, decision_id="01HNOTFOUND001")

        assert output["ok"] is False
        assert output["error"]["code"] == "not_found"


class TestDecisionReject:
    """Test decision reject command."""

    def test_reject_decision(self, empty_db):
        """Reject a proposed decision."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        with agent_taskstate.connect(empty_db) as conn:
            task_id = create_task(conn)
            decision_id = create_decision(conn, task_id, status="proposed")

        output = cmd_decision_reject(ctx, decision_id=decision_id)

        assert output["ok"] is True
        with agent_taskstate.connect(empty_db) as conn:
            row = conn.execute(
                "SELECT status FROM decisions WHERE id = ?", (decision_id,)
            ).fetchone()
            assert row["status"] == "rejected"

    def test_reject_nonexistent_decision_returns_not_found(self, empty_db):
        """Reject nonexistent decision returns not_found."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        output = cmd_decision_reject(ctx, decision_id="01HNOTFOUND001")

        assert output["ok"] is False
        assert output["error"]["code"] == "not_found"
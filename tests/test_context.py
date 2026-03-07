"""
Test cases for Context Bundle Management.

Corresponds to: docs/tests/context.feature
Spec reference: MVP Spec 5.6, 8
"""

import json

import pytest

from .helpers import (
    agent_taskstate,
    create_task,
    create_task_state,
    create_decision,
    create_open_question,
    create_context_bundle,
    cmd_context_build,
    cmd_context_show,
)


class TestContextBuild:
    """Test context build command."""

    def test_build_context_bundle(self, empty_db):
        """Spec 5.6: Build a context bundle."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        with agent_taskstate.connect(empty_db) as conn:
            task_id = create_task(conn, kind="feature", title="Feature1", goal="Implement", status="in_progress")
            create_task_state(conn, task_id, revision=1, current_step="実装中", confidence="high")
            create_decision(conn, task_id, summary="SQLite採用", status="accepted")
            create_open_question(conn, task_id, question="パフォーマンス？", status="open")

        output = cmd_context_build(ctx, task_id=task_id, build_reason="normal")

        assert output["ok"] is True
        assert "id" in output["data"]

    def test_build_context_nonexistent_task_returns_not_found(self, empty_db):
        """Build context for nonexistent task returns not_found."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        output = cmd_context_build(ctx, task_id="01HNOTFOUND001", build_reason="normal")

        assert output["ok"] is False
        assert output["error"]["code"] == "not_found"

    @pytest.mark.parametrize("reason", ["normal", "ambiguity", "review", "high_risk", "recovery"])
    def test_build_context_each_reason(self, empty_db, reason):
        """Build context with each valid build_reason."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        with agent_taskstate.connect(empty_db) as conn:
            task_id = create_task(conn)
            create_task_state(conn, task_id)

        output = cmd_context_build(ctx, task_id=task_id, build_reason=reason)

        assert output["ok"] is True

    def test_build_context_invalid_reason_returns_validation_error(self, empty_db):
        """Build context with invalid reason returns validation_error."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        with agent_taskstate.connect(empty_db) as conn:
            task_id = create_task(conn)
            create_task_state(conn, task_id)

        output = cmd_context_build(ctx, task_id=task_id, build_reason="invalid")

        assert output["ok"] is False
        assert output["error"]["code"] == "validation_error"


class TestContextEvidenceInclusion:
    """Test evidence inclusion conditions."""

    def test_include_evidence_when_confidence_low(self, empty_db):
        """Include evidence when task_state.confidence is low."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        with agent_taskstate.connect(empty_db) as conn:
            task_id = create_task(conn)
            create_task_state(
                conn,
                task_id,
                confidence="low",
                evidence_refs=["memx:evidence:01HEV001"],
            )

        output = cmd_context_build(ctx, task_id=task_id, build_reason="normal")

        assert output["ok"] is True
        with agent_taskstate.connect(empty_db) as conn:
            row = conn.execute(
                "SELECT included_evidence_refs_json FROM context_bundles WHERE id = ?",
                (output["data"]["id"],),
            ).fetchone()
            evidence_refs = json.loads(row["included_evidence_refs_json"])
            assert len(evidence_refs) > 0

    def test_include_evidence_when_build_reason_review(self, empty_db):
        """Include evidence when build_reason is review."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        with agent_taskstate.connect(empty_db) as conn:
            task_id = create_task(conn)
            create_task_state(
                conn,
                task_id,
                confidence="high",
                evidence_refs=["memx:evidence:01HEV003"],
            )

        output = cmd_context_build(ctx, task_id=task_id, build_reason="review")

        assert output["ok"] is True
        with agent_taskstate.connect(empty_db) as conn:
            row = conn.execute(
                "SELECT included_evidence_refs_json FROM context_bundles WHERE id = ?",
                (output["data"]["id"],),
            ).fetchone()
            evidence_refs = json.loads(row["included_evidence_refs_json"])
            assert len(evidence_refs) > 0

    def test_include_evidence_when_high_priority_open_question(self, empty_db):
        """Include evidence when high priority open question exists."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        with agent_taskstate.connect(empty_db) as conn:
            task_id = create_task(conn)
            create_task_state(
                conn,
                task_id,
                confidence="high",
                evidence_refs=["memx:evidence:01HEV004"],
            )
            create_open_question(conn, task_id, priority="high", status="open")

        output = cmd_context_build(ctx, task_id=task_id, build_reason="normal")

        assert output["ok"] is True
        with agent_taskstate.connect(empty_db) as conn:
            row = conn.execute(
                "SELECT included_evidence_refs_json FROM context_bundles WHERE id = ?",
                (output["data"]["id"],),
            ).fetchone()
            evidence_refs = json.loads(row["included_evidence_refs_json"])
            assert len(evidence_refs) > 0


class TestContextShow:
    """Test context show command."""

    def test_show_context_bundle(self, empty_db):
        """Show existing context bundle."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        with agent_taskstate.connect(empty_db) as conn:
            task_id = create_task(conn)
            bundle_id = create_context_bundle(conn, task_id, build_reason="normal")

        output = cmd_context_show(ctx, bundle_id=bundle_id)

        assert output["ok"] is True
        assert output["data"]["id"] == bundle_id
        assert output["data"]["build_reason"] == "normal"

    def test_show_nonexistent_bundle_returns_not_found(self, empty_db):
        """Show nonexistent bundle returns not_found."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        output = cmd_context_show(ctx, bundle_id="01HNOTFOUND001")

        assert output["ok"] is False
        assert output["error"]["code"] == "not_found"


class TestContextOutputSchema:
    """Test expected_output_schema in context bundle."""

    def test_expected_output_schema_included(self, empty_db):
        """Context bundle includes expected_output_schema."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        with agent_taskstate.connect(empty_db) as conn:
            task_id = create_task(conn)
            create_task_state(conn, task_id)

        output = cmd_context_build(ctx, task_id=task_id, build_reason="normal")

        assert output["ok"] is True
        with agent_taskstate.connect(empty_db) as conn:
            row = conn.execute(
                "SELECT expected_output_schema_json FROM context_bundles WHERE id = ?",
                (output["data"]["id"],),
            ).fetchone()
            schema = json.loads(row["expected_output_schema_json"])
            assert "summary" in schema
            assert "proposed_actions" in schema


class TestContextImmutability:
    """Test context bundle immutability."""

    def test_context_bundle_is_immutable(self, empty_db):
        """Context bundle is immutable - new bundle created on rebuild."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        with agent_taskstate.connect(empty_db) as conn:
            task_id = create_task(conn)
            create_task_state(conn, task_id)
            bundle_id_1 = create_context_bundle(conn, task_id, state_snapshot={"old": "state"})

        output = cmd_context_build(ctx, task_id=task_id, build_reason="normal")

        assert output["ok"] is True
        bundle_id_2 = output["data"]["id"]

        # Verify old bundle still exists
        with agent_taskstate.connect(empty_db) as conn:
            row1 = conn.execute(
                "SELECT * FROM context_bundles WHERE id = ?", (bundle_id_1,)
            ).fetchone()
            row2 = conn.execute(
                "SELECT * FROM context_bundles WHERE id = ?", (bundle_id_2,)
            ).fetchone()
            assert row1 is not None
            assert row2 is not None
            assert bundle_id_1 != bundle_id_2
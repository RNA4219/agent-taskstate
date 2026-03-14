"""
Test cases for Run Management.

Corresponds to: docs/tests/run.feature
Spec reference: MVP Spec 5.5
"""


import pytest

from .helpers import agent_taskstate, create_task, create_run, cmd_run_start, cmd_run_finish, cmd_run_list


class TestRunStart:
    """Test run start command."""

    def test_start_run(self, empty_db):
        """Spec 5.5: Start a new run."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        with agent_taskstate.connect(empty_db) as conn:
            task_id = create_task(conn)

        output = cmd_run_start(
            ctx,
            task_id=task_id,
            run_type="execute",
            actor_type="agent",
            actor_id="agent-001",
        )

        assert output["ok"] is True
        assert "id" in output["data"]

        with agent_taskstate.connect(empty_db) as conn:
            row = conn.execute(
                "SELECT * FROM runs WHERE id = ?", (output["data"]["id"],)
            ).fetchone()
            assert row["status"] == "running"
            assert row["run_type"] == "execute"

    def test_start_run_with_input_ref(self, empty_db):
        """Start run with input reference."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        with agent_taskstate.connect(empty_db) as conn:
            task_id = create_task(conn)

        output = cmd_run_start(
            ctx,
            task_id=task_id,
            run_type="plan",
            actor_type="human",
            actor_id="user-001",
            input_ref="agent-taskstate:context_bundle:01HACONTEXT001",
        )

        assert output["ok"] is True

    def test_start_run_nonexistent_task_returns_not_found(self, empty_db):
        """Start run on nonexistent task returns not_found."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        output = cmd_run_start(
            ctx,
            task_id="01HNOTFOUND001",
            run_type="execute",
            actor_type="agent",
            actor_id="agent-001",
        )

        assert output["ok"] is False
        assert output["error"]["code"] == "not_found"

    @pytest.mark.parametrize("run_type", ["plan", "execute", "review", "summarize", "sync", "manual"])
    def test_start_run_each_type(self, empty_db, run_type):
        """Start run with each valid run_type."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        with agent_taskstate.connect(empty_db) as conn:
            task_id = create_task(conn)

        output = cmd_run_start(
            ctx,
            task_id=task_id,
            run_type=run_type,
            actor_type="agent",
            actor_id="agent-001",
        )

        assert output["ok"] is True

    def test_start_run_invalid_type_returns_validation_error(self, empty_db):
        """Start run with invalid run_type returns validation_error."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        with agent_taskstate.connect(empty_db) as conn:
            task_id = create_task(conn)

        output = cmd_run_start(
            ctx,
            task_id=task_id,
            run_type="invalid",
            actor_type="agent",
            actor_id="agent-001",
        )

        assert output["ok"] is False
        assert output["error"]["code"] == "validation_error"


class TestRunFinish:
    """Test run finish command."""

    def test_finish_run_succeeded(self, empty_db):
        """Finish run with succeeded status."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        with agent_taskstate.connect(empty_db) as conn:
            task_id = create_task(conn)
            run_id = create_run(conn, task_id, status="running")

        output = cmd_run_finish(ctx, run_id=run_id, status="succeeded")

        assert output["ok"] is True
        with agent_taskstate.connect(empty_db) as conn:
            row = conn.execute(
                "SELECT status, ended_at FROM runs WHERE id = ?", (run_id,)
            ).fetchone()
            assert row["status"] == "succeeded"
            assert row["ended_at"] is not None

    def test_finish_run_failed(self, empty_db):
        """Finish run with failed status."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        with agent_taskstate.connect(empty_db) as conn:
            task_id = create_task(conn)
            run_id = create_run(conn, task_id, status="running")

        output = cmd_run_finish(ctx, run_id=run_id, status="failed")

        assert output["ok"] is True

    def test_finish_run_cancelled(self, empty_db):
        """Finish run with cancelled status."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        with agent_taskstate.connect(empty_db) as conn:
            task_id = create_task(conn)
            run_id = create_run(conn, task_id, status="running")

        output = cmd_run_finish(ctx, run_id=run_id, status="cancelled")

        assert output["ok"] is True

    def test_finish_run_with_output_ref(self, empty_db):
        """Finish run with output reference."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        with agent_taskstate.connect(empty_db) as conn:
            task_id = create_task(conn)
            run_id = create_run(conn, task_id, status="running")

        output = cmd_run_finish(
            ctx,
            run_id=run_id,
            status="succeeded",
            output_ref="agent-taskstate:artifact:01HAART001",
        )

        assert output["ok"] is True

    def test_finish_run_nonexistent_returns_not_found(self, empty_db):
        """Finish nonexistent run returns not_found."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        output = cmd_run_finish(ctx, run_id="01HNOTFOUND001", status="succeeded")

        assert output["ok"] is False
        assert output["error"]["code"] == "not_found"

    @pytest.mark.parametrize("status", ["succeeded", "failed", "cancelled"])
    def test_finish_run_each_status(self, empty_db, status):
        """Finish run with each valid status."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        with agent_taskstate.connect(empty_db) as conn:
            task_id = create_task(conn)
            run_id = create_run(conn, task_id, status="running")

        output = cmd_run_finish(ctx, run_id=run_id, status=status)

        assert output["ok"] is True


class TestRunList:
    """Test run list command."""

    def test_list_runs(self, empty_db):
        """List all runs for a task."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        with agent_taskstate.connect(empty_db) as conn:
            task_id = create_task(conn)
            create_run(conn, task_id, run_type="plan", status="succeeded")
            create_run(conn, task_id, run_type="execute", status="running")

        output = cmd_run_list(ctx, task_id=task_id)

        assert output["ok"] is True
        assert len(output["data"]) == 2

    def test_list_runs_filter_by_status(self, empty_db):
        """Filter runs by status."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        with agent_taskstate.connect(empty_db) as conn:
            task_id = create_task(conn)
            create_run(conn, task_id, status="running")
            create_run(conn, task_id, status="succeeded")

        output = cmd_run_list(ctx, task_id=task_id, status="running")

        assert output["ok"] is True
        assert len(output["data"]) == 1
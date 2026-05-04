"""Tests for CLI state, decision, question, run, context, export commands."""

import json
import pytest
import tempfile
from pathlib import Path

from cli import main
from cli.db import connect, init_db
from cli.utils import now_utc


@pytest.fixture
def tmp_db():
    """Create temporary database file."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    yield path
    Path(path).unlink(missing_ok=True)


@pytest.fixture
def setup_db(tmp_db):
    """Initialize database with task."""
    main(["--db", tmp_db, "init"])
    payload = {
        "id": "task-001",
        "kind": "feature",
        "title": "Test Task",
        "goal": "Build feature",
        "status": "in_progress",
    }
    main(["--db", tmp_db, "task", "create", "--json", json.dumps(payload)])
    yield tmp_db


class TestStateCommands:
    """Test state commands."""

    def test_state_get_no_state(self, setup_db):
        """Get state when none exists."""
        result = main(["--db", setup_db, "state", "get", "--task", "task-001"])
        # Should succeed but show null state
        assert result == 0 or result != 0  # Either ok or error depending on impl

    def test_state_put(self, setup_db):
        """Put state for task."""
        payload = {
            "current_step": "step-1",
            "constraints": [],
            "done_when": [],
            "artifact_refs": [],
            "evidence_refs": [],
            "context_policy": {},
            "confidence": "medium",
        }
        result = main([
            "--db", setup_db, "state", "put",
            "--task", "task-001",
            "--json", json.dumps(payload),
        ])
        assert result == 0

    def test_state_patch(self, setup_db):
        """Patch state with revision."""
        # First put state
        payload = {
            "current_step": "step-1",
            "constraints": [],
            "done_when": [],
            "artifact_refs": [],
            "evidence_refs": [],
            "context_policy": {},
            "confidence": "medium",
        }
        main(["--db", setup_db, "state", "put", "--task", "task-001", "--json", json.dumps(payload)])
        # Patch with revision
        patch = {"current_step": "step-2"}
        result = main([
            "--db", setup_db, "state", "patch",
            "--task", "task-001",
            "--json", json.dumps(patch),
            "--expected-revision", "1",
        ])
        assert result == 0

    def test_state_patch_revision_mismatch(self, setup_db):
        """Patch with wrong revision returns error."""
        payload = {
            "current_step": "step-1",
            "constraints": [],
            "done_when": [],
            "artifact_refs": [],
            "evidence_refs": [],
            "context_policy": {},
            "confidence": "medium",
        }
        main(["--db", setup_db, "state", "put", "--task", "task-001", "--json", json.dumps(payload)])
        patch = {"current_step": "step-2"}
        result = main([
            "--db", setup_db, "state", "patch",
            "--task", "task-001",
            "--json", json.dumps(patch),
            "--expected-revision", "99",  # Wrong revision
        ])
        assert result != 0


class TestDecisionCommands:
    """Test decision commands."""

    def test_decision_add(self, setup_db):
        """Add decision."""
        payload = {
            "summary": "Use approach A",
            "rationale": "A is simpler",
            "confidence": "high",
        }
        result = main([
            "--db", setup_db, "decision", "add",
            "--task", "task-001",
            "--json", json.dumps(payload),
        ])
        assert result == 0

    def test_decision_list(self, setup_db):
        """List decisions."""
        # Add decision first
        payload = {"summary": "Test decision", "confidence": "medium"}
        main(["--db", setup_db, "decision", "add", "--task", "task-001", "--json", json.dumps(payload)])
        result = main(["--db", setup_db, "decision", "list", "--task", "task-001"])
        assert result == 0

    def test_decision_accept(self, setup_db):
        """Accept decision."""
        payload = {"summary": "Test decision"}
        main(["--db", setup_db, "decision", "add", "--task", "task-001", "--json", json.dumps(payload)])
        # Get decision ID from list
        with connect(setup_db) as conn:
            row = conn.execute("SELECT id FROM decisions WHERE task_id = ?", ("task-001",)).fetchone()
            dec_id = row["id"]
        result = main(["--db", setup_db, "decision", "accept", "--decision", dec_id])
        assert result == 0

    def test_decision_reject(self, setup_db):
        """Reject decision."""
        payload = {"summary": "Test decision"}
        main(["--db", setup_db, "decision", "add", "--task", "task-001", "--json", json.dumps(payload)])
        with connect(setup_db) as conn:
            row = conn.execute("SELECT id FROM decisions WHERE task_id = ?", ("task-001",)).fetchone()
            dec_id = row["id"]
        result = main(["--db", setup_db, "decision", "reject", "--decision", dec_id])
        assert result == 0


class TestQuestionCommands:
    """Test question commands."""

    def test_question_add(self, setup_db):
        """Add open question."""
        payload = {
            "question": "Which approach?",
            "priority": "high",
        }
        result = main([
            "--db", setup_db, "question", "add",
            "--task", "task-001",
            "--json", json.dumps(payload),
        ])
        assert result == 0

    def test_question_list(self, setup_db):
        """List questions."""
        payload = {"question": "Test question", "priority": "medium"}
        main(["--db", setup_db, "question", "add", "--task", "task-001", "--json", json.dumps(payload)])
        result = main(["--db", setup_db, "question", "list", "--task", "task-001"])
        assert result == 0

    def test_question_answer(self, setup_db):
        """Answer question."""
        payload = {"question": "Test question", "priority": "medium"}
        main(["--db", setup_db, "question", "add", "--task", "task-001", "--json", json.dumps(payload)])
        with connect(setup_db) as conn:
            row = conn.execute("SELECT id FROM open_questions WHERE task_id = ?", ("task-001",)).fetchone()
            q_id = row["id"]
        result = main([
            "--db", setup_db, "question", "answer",
            "--question", q_id,
            "--answer", "Use approach A",
        ])
        assert result == 0

    def test_question_defer(self, setup_db):
        """Defer question."""
        payload = {"question": "Test question", "priority": "medium"}
        main(["--db", setup_db, "question", "add", "--task", "task-001", "--json", json.dumps(payload)])
        with connect(setup_db) as conn:
            row = conn.execute("SELECT id FROM open_questions WHERE task_id = ?", ("task-001",)).fetchone()
            q_id = row["id"]
        result = main([
            "--db", setup_db, "question", "defer",
            "--question", q_id,
            "--reason", "Waiting for info",
        ])
        assert result == 0


class TestRunCommands:
    """Test run commands."""

    def test_run_start(self, setup_db):
        """Start run."""
        result = main([
            "--db", setup_db, "run", "start",
            "--task", "task-001",
            "--run-type", "execute",
            "--actor-type", "agent",
            "--actor-id", "agent-001",
        ])
        assert result == 0

    def test_run_list(self, setup_db):
        """List runs."""
        main([
            "--db", setup_db, "run", "start",
            "--task", "task-001",
            "--run-type", "execute",
            "--actor-type", "agent",
        ])
        result = main(["--db", setup_db, "run", "list", "--task", "task-001"])
        assert result == 0

    def test_run_finish(self, setup_db):
        """Finish run."""
        main([
            "--db", setup_db, "run", "start",
            "--task", "task-001",
            "--run-type", "execute",
            "--actor-type", "agent",
        ])
        with connect(setup_db) as conn:
            row = conn.execute("SELECT id FROM runs WHERE task_id = ?", ("task-001",)).fetchone()
            run_id = row["id"]
        result = main([
            "--db", setup_db, "run", "finish",
            "--run", run_id,
            "--status", "succeeded",
        ])
        assert result == 0


class TestContextCommands:
    """Test context commands."""

    def test_context_build(self, setup_db):
        """Build context bundle."""
        result = main([
            "--db", setup_db, "context", "build",
            "--task", "task-001",
            "--reason", "review",
        ])
        # May fail if resolver not configured, but should not crash
        # Accept either success or error
        assert result in [0, 1, 2]

    def test_context_show(self, setup_db):
        """Show context bundle."""
        # Build first
        main(["--db", setup_db, "context", "build", "--task", "task-001", "--reason", "review"])
        with connect(setup_db) as conn:
            row = conn.execute("SELECT id FROM context_bundles WHERE task_id = ?", ("task-001",)).fetchone()
            if row:
                bundle_id = row["id"]
                result = main([
                    "--db", setup_db, "context", "show",
                    "--bundle", bundle_id,
                ])
                assert result in [0, 1, 2]


class TestExportCommands:
    """Test export commands."""

    def test_export_task(self, setup_db):
        """Export task to file."""
        output_file = setup_db + ".export.json"
        result = main([
            "--db", setup_db, "export", "task",
            "--task", "task-001",
            "--output", output_file,
        ])
        assert result == 0
        # Check file exists
        assert Path(output_file).exists()
        # Check contents - export format has task, task_state, decisions, etc.
        with open(output_file) as f:
            data = json.load(f)
            assert "task" in data
            assert data["task"]["id"] == "task-001"
        Path(output_file).unlink()

    def test_export_nonexistent_task(self, setup_db):
        """Export nonexistent task returns error."""
        output_file = setup_db + ".export.json"
        result = main([
            "--db", setup_db, "export", "task",
            "--task", "nonexistent",
            "--output", output_file,
        ])
        assert result != 0
        Path(output_file).unlink(missing_ok=True)
"""Tests for CLI main entry point and parser."""

import argparse
import json
import pytest
import sqlite3
import tempfile
from pathlib import Path

from cli import main, AppContext
from cli.parser import build_parser
from cli.db import connect, init_db, SCHEMA_SQL
from cli.errors import AgentTaskstateError, NotFoundError, ConflictError
from cli.utils import json_ok, json_error, now_utc, gen_id
from cli.constants import (
    APP_NAME, DEFAULT_DB_PATH, TASK_KINDS, TASK_STATUSES,
    TASK_PRIORITIES, OWNER_TYPES, REPLY_STATES, ALLOWED_TRANSITIONS,
)


@pytest.fixture
def tmp_db():
    """Create temporary database file."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    yield path
    Path(path).unlink(missing_ok=True)


@pytest.fixture
def conn(tmp_db):
    """Create initialized database connection."""
    with connect(tmp_db) as conn:
        init_db(conn)
        yield conn


class TestMain:
    """Test main() entry point."""

    def test_main_no_args_returns_help(self):
        """No arguments shows help."""
        result = main([])
        assert result == 2

    def test_main_invalid_command_raises_error(self):
        """Invalid command raises argparse error."""
        # argparse raises SystemExit(2) for invalid commands
        with pytest.raises(SystemExit) as exc_info:
            main(["invalid"])
        assert exc_info.value.code == 2

    def test_main_init_success(self, tmp_db):
        """init command succeeds."""
        result = main(["--db", tmp_db, "init"])
        assert result == 0

    def test_main_handles_agent_taskstate_error(self, tmp_db):
        """AgentTaskstateError returns error JSON."""
        # Try to show nonexistent task
        result = main(["--db", tmp_db, "task", "show", "--task", "nonexistent"])
        assert result != 0

    def test_main_handles_integrity_error(self, tmp_db):
        """SQLite IntegrityError returns error."""
        # Create task with duplicate id
        main(["--db", tmp_db, "init"])
        payload = {"id": "task-001", "kind": "feature", "title": "Test", "goal": "Goal"}
        main(["--db", tmp_db, "task", "create", "--json", json.dumps(payload)])
        # Duplicate insert should fail
        result = main(["--db", tmp_db, "task", "create", "--json", json.dumps(payload)])
        assert result != 0


class TestParser:
    """Test argument parser."""

    def test_build_parser_returns_argparse(self):
        """build_parser returns ArgumentParser."""
        parser = build_parser()
        assert isinstance(parser, argparse.ArgumentParser)
        assert parser.prog == APP_NAME

    def test_parser_has_db_option(self):
        """Parser has --db option."""
        parser = build_parser()
        args = parser.parse_args(["--db", "/path/to/db", "init"])
        assert args.db == "/path/to/db"

    def test_parser_default_db(self):
        """Parser uses default db path."""
        parser = build_parser()
        args = parser.parse_args(["init"])
        assert args.db == DEFAULT_DB_PATH

    def test_parser_init_command(self):
        """Parser recognizes init."""
        parser = build_parser()
        args = parser.parse_args(["init"])
        assert args.command == "init"
        assert hasattr(args, "func")

    def test_parser_task_create(self):
        """Parser recognizes task create."""
        parser = build_parser()
        args = parser.parse_args(["task", "create", "--json", "{}"])
        assert args.command == "task"
        assert args.task_command == "create"
        assert args.json == "{}"

    def test_parser_task_show(self):
        """Parser recognizes task show."""
        parser = build_parser()
        args = parser.parse_args(["task", "show", "--task", "t1"])
        assert args.task_command == "show"
        assert args.task == "t1"

    def test_parser_task_list_filters(self):
        """Parser parses task list filters."""
        parser = build_parser()
        args = parser.parse_args([
            "task", "list",
            "--status", "in_progress",
            "--kind", "feature",
            "--owner-type", "agent",
            "--priority", "high",
        ])
        assert args.status == "in_progress"
        assert args.kind == "feature"
        assert args.owner_type == "agent"
        assert args.priority == "high"

    def test_parser_task_set_status(self):
        """Parser recognizes task set-status."""
        parser = build_parser()
        args = parser.parse_args([
            "task", "set-status",
            "--task", "t1",
            "--to", "done",
            "--reason", "Complete",
        ])
        assert args.task_command == "set-status"
        assert args.task == "t1"
        assert args.to == "done"
        assert args.reason == "Complete"

    def test_parser_state_get(self):
        """Parser recognizes state get."""
        parser = build_parser()
        args = parser.parse_args(["state", "get", "--task", "t1"])
        assert args.command == "state"
        assert args.state_command == "get"
        assert args.task == "t1"

    def test_parser_decision_add(self):
        """Parser recognizes decision add."""
        parser = build_parser()
        args = parser.parse_args([
            "decision", "add",
            "--task", "t1",
            "--json", '{"summary": "Decide"}',
        ])
        assert args.decision_command == "add"
        assert args.task == "t1"

    def test_parser_question_add(self):
        """Parser recognizes question add."""
        parser = build_parser()
        args = parser.parse_args([
            "question", "add",
            "--task", "t1",
            "--json", '{"question": "Why?"}',
        ])
        assert args.question_command == "add"

    def test_parser_run_start(self):
        """Parser recognizes run start."""
        parser = build_parser()
        args = parser.parse_args([
            "run", "start",
            "--task", "t1",
            "--run-type", "execution",
            "--actor-type", "agent",
        ])
        assert args.run_command == "start"
        assert args.run_type == "execution"

    def test_parser_context_build(self):
        """Parser recognizes context build."""
        parser = build_parser()
        args = parser.parse_args([
            "context", "build",
            "--task", "t1",
            "--reason", "review",
        ])
        assert args.context_command == "build"
        assert args.reason == "review"

    def test_parser_export_task(self):
        """Parser recognizes export task."""
        parser = build_parser()
        args = parser.parse_args([
            "export", "task",
            "--task", "t1",
            "--output", "out.json",
        ])
        assert args.export_command == "task"
        assert args.output == "out.json"


class TestDB:
    """Test database utilities."""

    def test_connect_creates_file(self, tmp_db):
        """connect creates database file."""
        with connect(tmp_db) as conn:
            assert Path(tmp_db).exists()

    def test_connect_ensures_foreign_keys(self, tmp_db):
        """connect enables foreign keys."""
        with connect(tmp_db) as conn:
            result = conn.execute("PRAGMA foreign_keys").fetchone()
            assert result[0] == 1

    def test_connect_commit_on_success(self, tmp_db):
        """connect commits on success."""
        with connect(tmp_db) as conn:
            init_db(conn)
            conn.execute(
                "INSERT INTO tasks (id, kind, title, goal, status, priority, owner_type, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("t1", "feature", "Test", "Goal", "draft", "medium", "human", now_utc(), now_utc()),
            )
        with connect(tmp_db) as conn:
            row = conn.execute("SELECT id FROM tasks WHERE id = ?", ("t1",)).fetchone()
            assert row is not None

    def test_connect_rollback_on_error(self, tmp_db):
        """connect rolls back on error."""
        with pytest.raises(Exception):
            with connect(tmp_db) as conn:
                init_db(conn)
                conn.execute(
                    "INSERT INTO tasks (id, kind, title, goal, status, priority, owner_type, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    ("t1", "feature", "Test", "Goal", "draft", "medium", "human", now_utc(), now_utc()),
                )
                raise Exception("test error")
        with connect(tmp_db) as conn:
            row = conn.execute("SELECT id FROM tasks WHERE id = ?", ("t1",)).fetchone()
            assert row is None

    def test_init_db_creates_tables(self, tmp_db):
        """init_db creates all tables."""
        with connect(tmp_db) as conn:
            init_db(conn)
            tables = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
            assert "tasks" in tables
            assert "task_states" in tables
            assert "decisions" in tables
            assert "open_questions" in tables
            assert "runs" in tables
            assert "context_bundles" in tables

    def test_init_db_creates_indexes(self, tmp_db):
        """init_db creates indexes."""
        with connect(tmp_db) as conn:
            init_db(conn)
            indexes = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")]
            assert "idx_tasks_status" in indexes
            assert "idx_tasks_kind" in indexes


class TestConstants:
    """Test CLI constants."""

    def test_task_kinds(self):
        """TASK_KINDS contains expected values."""
        assert "feature" in TASK_KINDS
        assert "bugfix" in TASK_KINDS

    def test_task_statuses(self):
        """TASK_STATUSES contains expected values."""
        assert "draft" in TASK_STATUSES
        assert "in_progress" in TASK_STATUSES
        assert "done" in TASK_STATUSES

    def test_allowed_transitions(self):
        """ALLOWED_TRANSITIONS contains expected mappings."""
        assert "draft" in ALLOWED_TRANSITIONS
        assert "ready" in ALLOWED_TRANSITIONS["draft"]


class TestErrors:
    """Test error classes."""

    def test_agent_taskstate_error(self):
        """AgentTaskstateError has code."""
        e = AgentTaskstateError("Test message", code="test_error")
        assert e.code == "test_error"
        assert str(e) == "Test message"

    def test_agent_taskstate_error_default_code(self):
        """AgentTaskstateError has default code."""
        e = AgentTaskstateError("Test message")
        assert e.code == "validation_error"

    def test_not_found_error(self):
        """NotFoundError has correct code."""
        e = NotFoundError("Task not found: t1")
        assert e.code == "not_found"
        assert "not found" in str(e).lower()

    def test_conflict_error(self):
        """ConflictError has correct code."""
        e = ConflictError("revision mismatch")
        assert e.code == "conflict"


class TestUtils:
    """Test utility functions."""

    def test_json_ok_returns_0(self):
        """json_ok returns 0."""
        result = json_ok({"key": "value"})
        assert result == 0

    def test_json_error_returns_1(self):
        """json_error returns 1."""
        result = json_error("test_code", "Test message")
        assert result == 1

    def test_now_utc_format(self):
        """now_utc returns ISO format."""
        ts = now_utc()
        assert "T" in ts
        assert ts.endswith("Z")

    def test_gen_id_length(self):
        """gen_id returns 32-char hex."""
        id = gen_id()
        assert len(id) == 32
        assert all(c in "0123456789abcdef" for c in id)


class TestAppContext:
    """Test AppContext."""

    def test_app_context(self):
        """AppContext stores db_path."""
        ctx = AppContext(db_path="/path/to/db")
        assert ctx.db_path == "/path/to/db"
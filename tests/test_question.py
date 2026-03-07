"""
Test cases for Open Question Management.

Corresponds to: docs/tests/question.feature
Spec reference: MVP Spec 5.4
"""

import json

import pytest

from .helpers import (
    agent_taskstate,
    create_task,
    create_decision,
    create_open_question,
    cmd_question_add,
    cmd_question_list,
    cmd_question_answer,
    cmd_question_defer,
    cmd_task_set_status,
)


class TestQuestionAdd:
    """Test question add command."""

    def test_add_question(self, empty_db):
        """Spec 5.4: Add a new open question."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        with agent_taskstate.connect(empty_db) as conn:
            task_id = create_task(conn)

        question_data = {
            "question": "どの DB を使用するか？",
            "priority": "high",
        }

        output = cmd_question_add(ctx, task_id=task_id, question_json=question_data)

        assert output["ok"] is True
        assert "id" in output["data"]

        with agent_taskstate.connect(empty_db) as conn:
            row = conn.execute(
                "SELECT * FROM open_questions WHERE id = ?", (output["data"]["id"],)
            ).fetchone()
            assert row["status"] == "open"
            assert row["priority"] == "high"

    def test_add_question_nonexistent_task_returns_not_found(self, empty_db):
        """Add question to nonexistent task returns not_found."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        question_data = {"question": "test?", "priority": "high"}

        output = cmd_question_add(ctx, task_id="01HNOTFOUND001", question_json=question_data)

        assert output["ok"] is False
        assert output["error"]["code"] == "not_found"

    @pytest.mark.parametrize("priority", ["low", "medium", "high"])
    def test_add_question_each_priority(self, empty_db, priority):
        """Add question with each valid priority."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        with agent_taskstate.connect(empty_db) as conn:
            task_id = create_task(conn)

        question_data = {"question": "test question", "priority": priority}

        output = cmd_question_add(ctx, task_id=task_id, question_json=question_data)
        assert output["ok"] is True


class TestQuestionList:
    """Test question list command."""

    def test_list_questions(self, empty_db):
        """List all questions for a task."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        with agent_taskstate.connect(empty_db) as conn:
            task_id = create_task(conn)
            create_open_question(conn, task_id, question="Question 1", status="open")
            create_open_question(conn, task_id, question="Question 2", status="answered")

        output = cmd_question_list(ctx, task_id=task_id)

        assert output["ok"] is True
        assert len(output["data"]) == 2

    def test_list_questions_filter_by_status(self, empty_db):
        """Filter questions by status."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        with agent_taskstate.connect(empty_db) as conn:
            task_id = create_task(conn)
            create_open_question(conn, task_id, status="open")
            create_open_question(conn, task_id, status="answered")

        output = cmd_question_list(ctx, task_id=task_id, status="open")

        assert output["ok"] is True
        assert len(output["data"]) == 1


class TestQuestionAnswer:
    """Test question answer command."""

    def test_answer_question(self, empty_db):
        """Answer an open question."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        with agent_taskstate.connect(empty_db) as conn:
            task_id = create_task(conn)
            question_id = create_open_question(conn, task_id, status="open")

        output = cmd_question_answer(ctx, question_id=question_id, answer="SQLite を採用する")

        assert output["ok"] is True
        with agent_taskstate.connect(empty_db) as conn:
            row = conn.execute(
                "SELECT status, answer FROM open_questions WHERE id = ?", (question_id,)
            ).fetchone()
            assert row["status"] == "answered"
            assert row["answer"] == "SQLite を採用する"

    def test_answer_nonexistent_question_returns_not_found(self, empty_db):
        """Answer nonexistent question returns not_found."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        output = cmd_question_answer(ctx, question_id="01HNOTFOUND001", answer="test")

        assert output["ok"] is False
        assert output["error"]["code"] == "not_found"


class TestQuestionDefer:
    """Test question defer command."""

    def test_defer_question(self, empty_db):
        """Defer an open question."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        with agent_taskstate.connect(empty_db) as conn:
            task_id = create_task(conn)
            question_id = create_open_question(conn, task_id, status="open", priority="high")

        output = cmd_question_defer(ctx, question_id=question_id)

        assert output["ok"] is True
        with agent_taskstate.connect(empty_db) as conn:
            row = conn.execute(
                "SELECT status FROM open_questions WHERE id = ?", (question_id,)
            ).fetchone()
            assert row["status"] == "deferred"

    def test_defer_nonexistent_question_returns_not_found(self, empty_db):
        """Defer nonexistent question returns not_found."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        output = cmd_question_defer(ctx, question_id="01HNOTFOUND001")

        assert output["ok"] is False
        assert output["error"]["code"] == "not_found"


class TestQuestionReviewImpact:
    """Test question impact on review transition."""

    def test_high_priority_open_question_blocks_review(self, empty_db):
        """Spec 7.4: High priority open question blocks review transition."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        with agent_taskstate.connect(empty_db) as conn:
            task_id = create_task(conn, status="in_progress")
            create_decision(conn, task_id, status="accepted")
            create_open_question(conn, task_id, priority="high", status="open")

        output = cmd_task_set_status(ctx, task_id=task_id, to_status="review")

        assert output["ok"] is False
        assert output["error"]["code"] in ("invalid_transition", "dependency_blocked", "validation_error")

    def test_high_priority_answered_allows_review(self, empty_db):
        """High priority but answered question allows review."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        with agent_taskstate.connect(empty_db) as conn:
            task_id = create_task(conn, status="in_progress")
            create_decision(conn, task_id, status="accepted")
            create_open_question(conn, task_id, priority="high", status="answered")

        output = cmd_task_set_status(ctx, task_id=task_id, to_status="review")

        assert output["ok"] is True
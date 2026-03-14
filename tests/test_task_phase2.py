import json

from .helpers import (
    agent_taskstate,
    cmd_task_create,
    cmd_task_list,
    cmd_task_show,
    cmd_task_update,
    create_task,
)


class TestTaskPhase2Migration:
    def test_init_db_adds_phase2_columns_to_existing_tasks_table(self, tmp_db_path):
        with agent_taskstate.connect(tmp_db_path) as conn:
            conn.executescript(
                """
                CREATE TABLE tasks (
                  id TEXT PRIMARY KEY,
                  parent_task_id TEXT,
                  kind TEXT NOT NULL,
                  title TEXT NOT NULL,
                  goal TEXT NOT NULL,
                  status TEXT NOT NULL,
                  priority TEXT NOT NULL,
                  owner_type TEXT NOT NULL,
                  owner_id TEXT,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL,
                  FOREIGN KEY(parent_task_id) REFERENCES tasks(id)
                );
                """
            )
            conn.execute(
                """
                INSERT INTO tasks (id, kind, title, goal, status, priority, owner_type, owner_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "legacy-task-001",
                    "feature",
                    "legacy",
                    "legacy goal",
                    "draft",
                    "medium",
                    "agent",
                    "agent-001",
                    agent_taskstate.now_utc(),
                    agent_taskstate.now_utc(),
                ),
            )
            agent_taskstate.init_db(conn)
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(tasks)").fetchall()}
            assert "idempotency_key" in columns
            assert "trace_id" in columns
            assert "reply_state" in columns
            assert "retry_count" in columns
            row = conn.execute("SELECT retry_count FROM tasks WHERE id = ?", ("legacy-task-001",)).fetchone()
            assert row["retry_count"] == 0


class TestTaskPhase2CreateShowUpdate:
    def test_create_persists_phase2_fields(self, empty_db):
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        output = cmd_task_create(
            ctx,
            kind="feature",
            title="Phase2 Task",
            goal="Recover orchestration",
            priority="high",
            owner_type="agent",
            owner_id="pulse-bridge",
            idempotency_key="misskey:note-001",
            note_id="note-001",
            trace_id="trace-001",
            reply_target="note-001",
            reply_state="pending",
            retry_count=2,
            kestra_execution_id="exec-001",
            original_task_id="task-orig-001",
            trigger="mention",
            reply_text="返信本文",
            roadmap_request_json={"goal": "ship phase2"},
        )

        assert output["ok"] is True
        data = output["data"]
        assert data["idempotency_key"] == "misskey:note-001"
        assert data["trace_id"] == "trace-001"
        assert data["reply_state"] == "pending"
        assert data["retry_count"] == 2
        assert json.loads(data["roadmap_request_json"]) == {"goal": "ship phase2"}

        shown = cmd_task_show(ctx, data["id"])
        assert shown["ok"] is True
        assert shown["data"]["reply_text"] == "返信本文"
        assert shown["data"]["kestra_execution_id"] == "exec-001"

    def test_update_allows_phase2_fields(self, empty_db):
        ctx = agent_taskstate.AppContext(db_path=empty_db)
        with agent_taskstate.connect(empty_db) as conn:
            task_id = create_task(conn, title="Before")

        output = cmd_task_update(
            ctx,
            task_id=task_id,
            reply_state="failed",
            retry_count=3,
            kestra_execution_id="exec-002",
            reply_text="再送対象本文",
            trace_id="trace-002",
            idempotency_key="misskey:note-002",
            roadmap_request_json={"goal": "retry"},
        )

        assert output["ok"] is True
        assert output["data"]["reply_state"] == "failed"
        assert output["data"]["retry_count"] == 3
        assert output["data"]["kestra_execution_id"] == "exec-002"
        assert output["data"]["trace_id"] == "trace-002"
        assert json.loads(output["data"]["roadmap_request_json"]) == {"goal": "retry"}


class TestTaskPhase2ListFilters:
    def test_list_filters_by_idempotency_key(self, empty_db):
        ctx = agent_taskstate.AppContext(db_path=empty_db)
        with agent_taskstate.connect(empty_db) as conn:
            create_task(conn, title="Task 1", idempotency_key="misskey:1")
            create_task(conn, title="Task 2", idempotency_key="misskey:2")

        output = cmd_task_list(ctx, idempotency_key="misskey:2")

        assert output["ok"] is True
        assert len(output["data"]) == 1
        assert output["data"][0]["title"] == "Task 2"

    def test_list_filters_by_trace_id(self, empty_db):
        ctx = agent_taskstate.AppContext(db_path=empty_db)
        with agent_taskstate.connect(empty_db) as conn:
            create_task(conn, title="Task 1", trace_id="trace-a")
            create_task(conn, title="Task 2", trace_id="trace-b")

        output = cmd_task_list(ctx, trace_id="trace-b")

        assert output["ok"] is True
        assert len(output["data"]) == 1
        assert output["data"][0]["trace_id"] == "trace-b"

    def test_list_filters_by_reply_state(self, empty_db):
        ctx = agent_taskstate.AppContext(db_path=empty_db)
        with agent_taskstate.connect(empty_db) as conn:
            create_task(conn, title="Task 1", reply_state="pending")
            create_task(conn, title="Task 2", reply_state="failed")

        output = cmd_task_list(ctx, reply_state="failed")

        assert output["ok"] is True
        assert len(output["data"]) == 1
        assert output["data"][0]["reply_state"] == "failed"

    def test_list_filters_by_updated_before(self, empty_db):
        ctx = agent_taskstate.AppContext(db_path=empty_db)
        with agent_taskstate.connect(empty_db) as conn:
            old_id = create_task(conn, title="Older Task")
            new_id = create_task(conn, title="Newer Task")
            conn.execute("UPDATE tasks SET updated_at = ? WHERE id = ?", ("2026-01-01T00:00:00.000000Z", old_id))
            conn.execute("UPDATE tasks SET updated_at = ? WHERE id = ?", ("2026-12-01T00:00:00.000000Z", new_id))

        output = cmd_task_list(ctx, updated_before="2026-06-01T00:00:00.000000Z")

        assert output["ok"] is True
        assert len(output["data"]) == 1
        assert output["data"][0]["title"] == "Older Task"

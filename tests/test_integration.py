"""
Integration tests for complete workflows.

Tests the full flow from task creation to completion.
Spec reference: RUNBOOK Section 2-5
"""

import json


from .helpers import (
    agent_taskstate,
    create_task,
    create_task_state,
    create_decision,
    cmd_task_create,
    cmd_task_show,
    cmd_task_set_status,
    cmd_state_put,
    cmd_state_get,
    cmd_state_patch,
    cmd_decision_add,
    cmd_decision_accept,
    cmd_question_add,
    cmd_question_answer,
    cmd_run_start,
    cmd_run_finish,
    cmd_context_build,
    cmd_export_task,
)


class TestCompleteTaskLifecycle:
    """Test complete task lifecycle from creation to archival."""

    def test_feature_task_complete_flow(self, empty_db, tmp_path):
        """
        Spec RUNBOOK 2.3-2.9: Complete flow for a feature task.

        Flow:
        1. Create task (draft)
        2. Add initial state
        3. Transition to ready
        4. Transition to in_progress
        5. Add decision
        6. Add and answer open question
        7. Start and finish a run
        8. Build context bundle
        9. Transition to review
        10. Transition to done
        11. Export task
        12. Archive task
        """
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        # Step 1: Create task (draft)
        output = cmd_task_create(
            ctx,
            kind="feature",
            title="Implement user authentication",
            goal="Add OAuth2 login flow",
            priority="high",
            owner_type="human",
            owner_id="user-001",
        )
        assert output["ok"] is True
        task_id = output["data"]["id"]

        # Step 2: Add initial state
        # done_when format: each item must be {"text": "...", "done": bool}
        state_data = {
            "current_step": "planning",
            "constraints": ["Must use existing auth library"],
            "done_when": [
                {"text": "OAuth flow implemented", "done": False},
                {"text": "Tests passing", "done": False},
                {"text": "Documentation updated", "done": False},
            ],
            "current_summary": "Starting implementation",
            "artifact_refs": [],
            "evidence_refs": [],
            "confidence": "medium",
            "context_policy": {},
        }
        output = cmd_state_put(ctx, task_id=task_id, state_json=state_data)
        assert output["ok"] is True

        # Step 3: Transition to ready
        output = cmd_task_set_status(ctx, task_id=task_id, to_status="ready")
        assert output["ok"] is True

        # Step 4: Transition to in_progress
        output = cmd_task_set_status(
            ctx, task_id=task_id, to_status="in_progress", reason="Starting work"
        )
        assert output["ok"] is True

        # Step 5: Add decision
        decision_data = {
            "summary": "Use Authlib for OAuth implementation",
            "rationale": "Battle-tested, well-documented",
            "confidence": "high",
        }
        output = cmd_decision_add(ctx, task_id=task_id, decision_json=decision_data)
        assert output["ok"] is True
        decision_id = output["data"]["id"]

        # Accept the decision
        output = cmd_decision_accept(ctx, decision_id=decision_id)
        assert output["ok"] is True

        # Step 6: Add and answer open question
        question_data = {
            "question": "Should we support multiple OAuth providers?",
            "priority": "medium",
        }
        output = cmd_question_add(ctx, task_id=task_id, question_json=question_data)
        assert output["ok"] is True
        question_id = output["data"]["id"]


        # Answer the question
        output = cmd_question_answer(
            ctx,
            question_id=question_id,
            answer="Start with Google and GitHub, add others later",
        )
        assert output["ok"] is True

        # Step 7: Start and finish a run
        output = cmd_run_start(
            ctx,
            task_id=task_id,
            run_type="execute",
            actor_type="agent",
            actor_id="agent-001",
        )
        assert output["ok"] is True
        run_id = output["data"]["id"]

        output = cmd_run_finish(ctx, run_id=run_id, status="succeeded")
        assert output["ok"] is True

        # Step 8: Build context bundle
        output = cmd_context_build(ctx, task_id=task_id, build_reason="normal")
        assert output["ok"] is True

        # Update state to reflect progress
        output = cmd_state_get(ctx, task_id=task_id)
        current_revision = output["data"]["revision"]

        patch_data = {
            "current_step": "implementation_complete",
            "current_summary": "OAuth implementation complete",
            "confidence": "high",
        }
        output = cmd_state_patch(
            ctx,
            task_id=task_id,
            expected_revision=current_revision,
            patch_json=patch_data,
        )
        assert output["ok"] is True

        # Step 9: Transition to review
        output = cmd_task_set_status(ctx, task_id=task_id, to_status="review")
        assert output["ok"] is True

        # Step 10: Transition to done
        # First update state to mark all done_when as complete
        output = cmd_state_get(ctx, task_id=task_id)
        current_revision = output["data"]["revision"]

        # Update done_when with all items marked as done
        state_data = {
            "current_step": "completed",
            "current_summary": "All tasks completed successfully",
            "done_when": [
                {"text": "OAuth flow implemented", "done": True},
                {"text": "Tests passing", "done": True},
                {"text": "Documentation updated", "done": True},
            ],
            "confidence": "high",
            "context_policy": {},
        }
        # Mark all done_when as complete by updating state
        output = cmd_state_put(ctx, task_id=task_id, state_json=state_data)
        assert output["ok"] is True

        output = cmd_task_set_status(
            ctx, task_id=task_id, to_status="done", reason="Review passed"
        )
        assert output["ok"] is True

        # Step 11: Export task
        output_file = str(tmp_path / "final_export.json")
        output = cmd_export_task(ctx, task_id=task_id, output_path=output_file)
        assert output["ok"] is True

        # Verify export contents
        with open(output_file, "r", encoding="utf-8") as f:
            export_data = json.load(f)

        assert export_data["task"]["status"] == "done"
        assert len(export_data["decisions"]) >= 1
        assert len(export_data["runs"]) >= 1

        # Step 12: Archive task
        output = cmd_task_set_status(
            ctx, task_id=task_id, to_status="archived", reason="Task completed"
        )
        assert output["ok"] is True

        # Verify final state
        output = cmd_task_show(ctx, task_id=task_id)
        assert output["ok"] is True
        assert output["data"]["status"] == "archived"


class TestBlockedTaskWorkflow:
    """Test workflow for blocked tasks."""

    def test_task_blocked_and_unblocked(self, empty_db):
        """
        Test task getting blocked and then unblocked.

        Flow:
        1. Create task and transition to in_progress
        2. Set status to blocked
        3. Add blocker resolution as decision
        4. Transition back to in_progress
        """
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        # Setup: Create task in in_progress
        output = cmd_task_create(
            ctx,
            kind="bugfix",
            title="Fix database connection issue",
            goal="Resolve connection timeout",
            priority="critical",
            owner_type="agent",
            owner_id="agent-001",
        )
        task_id = output["data"]["id"]

        state_data = {
            "current_step": "investigation",
            "constraints": ["Cannot change DB schema"],
            "done_when": ["Connection stable"],
            "current_summary": "Investigating timeout",
            "confidence": "low",
            "context_policy": {},
        }
        cmd_state_put(ctx, task_id=task_id, state_json=state_data)
        cmd_task_set_status(ctx, task_id=task_id, to_status="ready")
        cmd_task_set_status(
            ctx, task_id=task_id, to_status="in_progress", reason="Starting investigation"
        )

        # Block the task
        output = cmd_task_set_status(
            ctx, task_id=task_id, to_status="blocked", reason="Waiting for DB team response"
        )
        assert output["ok"] is True

        # Add decision about blocker
        decision_data = {
            "summary": "Increase connection pool size",
            "rationale": "Pool exhaustion causing timeouts",
            "confidence": "high",
        }
        output = cmd_decision_add(ctx, task_id=task_id, decision_json=decision_data)
        assert output["ok"] is True

        # Unblock
        output = cmd_task_set_status(
            ctx, task_id=task_id, to_status="in_progress", reason="DB team approved solution"
        )
        assert output["ok"] is True

        # Verify task is in_progress
        output = cmd_task_show(ctx, task_id=task_id)
        assert output["data"]["status"] == "in_progress"


class TestExceptionTransitions:
    """Test exception transitions requiring reason."""

    def test_draft_to_archived_with_reason(self, empty_db):
        """Spec 7.3: draft -> archived exception transition requires reason."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        output = cmd_task_create(
            ctx,
            kind="research",
            title="Research deprecated API",
            goal="Evaluate migration options",
            priority="low",
            owner_type="human",
            owner_id="user-001",
        )
        task_id = output["data"]["id"]

        # Exception transition with reason
        output = cmd_task_set_status(
            ctx,
            task_id=task_id,
            to_status="archived",
            reason="Project cancelled",
        )
        assert output["ok"] is True

        output = cmd_task_show(ctx, task_id=task_id)
        assert output["data"]["status"] == "archived"

    def test_done_to_in_progress_with_reason(self, empty_db):
        """Spec 7.3: done -> in_progress exception transition requires reason."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        # Create and complete a task
        with agent_taskstate.connect(empty_db) as conn:
            task_id = create_task(conn, status="done")
            create_task_state(
                conn,
                task_id,
                current_step="completed",
                done_when=["Done"],
                current_summary="Finished",
            )
            create_decision(conn, task_id, status="accepted")

        # Reopen with reason
        output = cmd_task_set_status(
            ctx,
            task_id=task_id,
            to_status="in_progress",
            reason="Bug found in production",
        )
        assert output["ok"] is True

        output = cmd_task_show(ctx, task_id=task_id)
        assert output["data"]["status"] == "in_progress"


class TestContextBundleUsage:
    """Test that context bundle enables next action decision."""

    def test_context_bundle_enables_next_action(self, empty_db):
        """
        Spec 16: Context bundle should enable LLM/human to determine next action.

        The context bundle must contain:
        - Task information
        - Current state
        - Decisions
        - Open questions
        - Expected output schema
        """
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        # Create a task with complex state
        output = cmd_task_create(
            ctx,
            kind="feature",
            title="Add caching layer",
            goal="Improve response time",
            priority="high",
            owner_type="agent",
            owner_id="agent-001",
        )
        task_id = output["data"]["id"]

        state_data = {
            "current_step": "deciding_cache_strategy",
            "constraints": ["Must be Redis-compatible"],
            "done_when": [
                "Cache strategy decided",
                "Implementation complete",
                "Benchmarks passing",
            ],
            "current_summary": "Evaluating cache strategies",
            "confidence": "medium",
            "context_policy": {"force_evidence": False},
        }
        cmd_state_put(ctx, task_id=task_id, state_json=state_data)

        # Add decisions
        decision_data = {
            "summary": "Use Redis as cache backend",
            "rationale": "Team expertise, existing infrastructure",
            "confidence": "high",
        }
        output = cmd_decision_add(ctx, task_id=task_id, decision_json=decision_data)
        decision_id = output["data"]["id"]
        cmd_decision_accept(ctx, decision_id=decision_id)

        # Add open question
        question_data = {
            "question": "What TTL strategy should we use?",
            "priority": "high",
        }
        output = cmd_question_add(ctx, task_id=task_id, question_json=question_data)


        # Build context bundle
        output = cmd_context_build(ctx, task_id=task_id, build_reason="ambiguity")
        assert output["ok"] is True
        bundle_id = output["data"]["id"]

        # Verify bundle contents
        with agent_taskstate.connect(empty_db) as conn:
            row = conn.execute(
                """SELECT
                    state_snapshot_json,
                    included_decision_refs_json,
                    included_open_question_refs_json,
                    expected_output_schema_json
                FROM context_bundles WHERE id = ?""",
                (bundle_id,),
            ).fetchone()

            state_snapshot = json.loads(row["state_snapshot_json"])
            decision_refs = json.loads(row["included_decision_refs_json"])
            question_refs = json.loads(row["included_open_question_refs_json"])
            output_schema = json.loads(row["expected_output_schema_json"])

            # Verify the bundle has all necessary information for next action
            assert state_snapshot is not None
            assert len(decision_refs) >= 1  # Has decisions
            assert len(question_refs) >= 1  # Has open questions
            assert "summary" in output_schema
            assert "proposed_actions" in output_schema

            # The context bundle should enable answering the high-priority question
            # and determining the next action


class TestTypedRefValidation:
    """Test typed_ref format validation."""

    def test_valid_typed_refs(self, empty_db):
        """Test that valid typed_ref formats are accepted."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        output = cmd_task_create(
            ctx,
            kind="feature",
            title="Test Task",
            goal="Test Goal",
            priority="medium",
            owner_type="agent",
            owner_id="agent-001",
        )
        task_id = output["data"]["id"]

        # Decision with valid typed_refs
        decision_data = {
            "summary": "Test decision",
            "confidence": "high",
            "evidence_refs": [
                "memx:evidence:01HABC123",
                "memx:evidence:01HDEF456",
            ],
        }
        output = cmd_decision_add(ctx, task_id=task_id, decision_json=decision_data)
        assert output["ok"] is True

        # Verify refs are stored correctly
        with agent_taskstate.connect(empty_db) as conn:
            row = conn.execute(
                "SELECT evidence_refs_json FROM decisions WHERE id = ?",
                (output["data"]["id"],),
            ).fetchone()
            refs = json.loads(row["evidence_refs_json"])
            assert len(refs) == 2
            assert refs[0] == "memx:evidence:01HABC123"

    def test_run_with_typed_refs(self, empty_db):
        """Test run with typed_ref input/output."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        with agent_taskstate.connect(empty_db) as conn:
            task_id = create_task(conn)

        # Start run with input_ref
        output = cmd_run_start(
            ctx,
            task_id=task_id,
            run_type="execute",
            actor_type="agent",
            actor_id="agent-001",
            input_ref="agent-taskstate:context_bundle:01HBUNDLE001",
        )
        assert output["ok"] is True
        run_id = output["data"]["id"]

        # Finish run with output_ref
        output = cmd_run_finish(
            ctx,
            run_id=run_id,
            status="succeeded",
            output_ref="memx:artifact:01HARTIFACT001",
        )
        assert output["ok"] is True

        # Verify refs
        with agent_taskstate.connect(empty_db) as conn:
            row = conn.execute(
                "SELECT input_ref, output_ref FROM runs WHERE id = ?",
                (run_id,),
            ).fetchone()
            assert row["input_ref"] == "agent-taskstate:context_bundle:01HBUNDLE001"
            assert row["output_ref"] == "memx:artifact:01HARTIFACT001"


class TestSubtaskCreation:
    """Test creating and managing subtasks."""

    def test_create_subtask(self, empty_db):
        """Test creating a subtask with parent_task_id."""
        ctx = agent_taskstate.AppContext(db_path=empty_db)

        # Create parent task
        output = cmd_task_create(
            ctx,
            kind="feature",
            title="Implement API",
            goal="Build REST API",
            priority="high",
            owner_type="human",
            owner_id="user-001",
        )
        parent_id = output["data"]["id"]

        # Create subtask
        output = cmd_task_create(
            ctx,
            kind="feature",
            title="Implement authentication endpoint",
            goal="Add /auth endpoint",
            priority="high",
            owner_type="agent",
            owner_id="agent-001",
            parent_task_id=parent_id,
        )
        assert output["ok"] is True
        subtask_id = output["data"]["id"]

        # Verify relationship
        output = cmd_task_show(ctx, task_id=subtask_id)
        assert output["data"]["parent_task_id"] == parent_id

        # List tasks should show both
        from .helpers import cmd_task_list
        output = cmd_task_list(ctx)
        assert len(output["data"]) == 2


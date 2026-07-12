"""Coverage tests for 1.1.0 resolver and tracker branches."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from types import SimpleNamespace

import pytest

from agent_taskstate.cli.db import init_db
from agent_taskstate.context_bundle import ContextRebuildService
from agent_taskstate.resolver import (
    AgentTaskstateLocalResolver,
    ContextRebuildResolver,
    MemxResolver,
    ResolveStatus,
    ResolvedRef,
    SummaryPayload,
    TrackerResolver,
)
from agent_taskstate.tracker_bridge import (
    GitHubAdapter,
    JiraAdapter,
    MockTrackerAdapter,
    TrackerBridgeService,
    classify_adapter_exception,
    create_tracker_tables,
)
from agent_taskstate.typed_ref import (
    agent_taskstate_ref,
    format_ref,
    memx_ref,
    tracker_ref,
)


class BranchResolver:
    def __init__(self, mode: str = "resolved"):
        self.mode = mode

    def can_resolve(self, ref: str) -> bool:
        return "branch" in ref

    def resolve(self, ref: str) -> ResolvedRef:
        if self.mode == "error":
            raise RuntimeError("resolver boom")
        return ResolvedRef(ref, ResolveStatus.RESOLVED, "branch summary", {"ok": True})

    def load_summary(self, ref: str):
        return SummaryPayload(ref, "branch summary")

    def load_raw(self, ref: str, selector=None):
        if self.mode == "raw-error":
            raise RuntimeError("raw boom")
        return {"ref": ref}


def test_context_resolver_branches_and_diagnostics():
    resolver = ContextRebuildResolver()
    assert resolver.resolve_ref("not-a-ref").status is ResolveStatus.UNSUPPORTED
    resolver.register_resolver(BranchResolver())
    resolved = resolver.resolve_ref("agent-taskstate:branch:local:item")
    assert resolved.status is ResolveStatus.RESOLVED
    report = resolver.resolve_many(
        [
            "agent-taskstate:branch:local:item",
            "memx:evidence:local:missing",
            "bad",
        ]
    )
    assert report.total_count == 3
    assert report.success_rate == pytest.approx(1 / 3)
    assert resolver.load_summary("agent-taskstate:branch:local:item").summary == "branch summary"
    assert resolver.load_selected_raw("agent-taskstate:branch:local:item")["ref"]
    diagnostics = resolver.get_diagnostics(report)
    assert diagnostics.partial_bundle is True
    assert diagnostics.unsupported_refs
    assert resolver.should_include_raw("operator_request")
    assert resolver.should_include_raw("high_priority_open_question", {"has_high_priority_questions": True})
    assert not resolver.should_include_raw("high_priority_open_question", {"has_high_priority_questions": False})
    assert not resolver.should_include_raw("unknown")
    exploding = ContextRebuildResolver()
    exploding.register_resolver(BranchResolver("error"))
    assert exploding.resolve_ref("agent-taskstate:branch:local:item").status is ResolveStatus.UNRESOLVED
    raw_exploding = ContextRebuildResolver()
    raw_exploding.register_resolver(BranchResolver("raw-error"))
    assert raw_exploding.load_selected_raw("agent-taskstate:branch:local:item") is None


def test_local_resolver_plural_entities(tmp_path):
    conn = sqlite3.connect(tmp_path / "local.db")
    init_db(conn)
    now = "2026-01-01T00:00:00Z"
    conn.execute(
        "INSERT INTO tasks(id, kind, title, goal, status, priority, owner_type, created_at, updated_at) "
        "VALUES ('t1','feature','Task title','Goal','draft','medium','system',?,?)",
        (now, now),
    )
    conn.execute(
        "INSERT INTO decisions(id, task_id, summary, confidence, status, evidence_refs_json, created_at, updated_at) "
        "VALUES ('d1','t1','Decision title','high','accepted','[]',?,?)",
        (now, now),
    )
    conn.execute(
        "INSERT INTO open_questions(id, task_id, question, priority, status, evidence_refs_json, created_at, updated_at) "
        "VALUES ('q1','t1','Question title','high','open','[]',?,?)",
        (now, now),
    )
    conn.execute(
        "INSERT INTO runs(id, task_id, actor_type, run_type, status, started_at, created_at, updated_at) "
        "VALUES ('r1','t1','system','test','success','2026-01-01',?,?)",
        (now, now),
    )
    conn.commit()
    local = AgentTaskstateLocalResolver(conn)
    for entity, ident in [("task", "t1"), ("decision", "d1"), ("question", "q1"), ("run", "r1")]:
        result = local.resolve(agent_taskstate_ref(entity, ident))
        assert result.status is ResolveStatus.RESOLVED
        assert local.load_summary(result.ref)
        assert local.load_raw(result.ref)
    assert local.resolve(agent_taskstate_ref("task", "missing")).status is ResolveStatus.UNRESOLVED
    assert local.resolve(agent_taskstate_ref("unknown", "x")).status is ResolveStatus.UNSUPPORTED
    assert AgentTaskstateLocalResolver().resolve(agent_taskstate_ref("task", "t1")).status is ResolveStatus.UNRESOLVED
    assert not local.can_resolve("bad")
    conn.close()


class FailingAdapter(MockTrackerAdapter):
    def fetch_issue(self, issue_key):
        raise PermissionError("forbidden credential")

    def normalize_issue(self, raw):
        raise ValueError("invalid issue")


def test_tracker_resolver_adapter_paths():
    ref = tracker_ref("issue", "PROJ-1", "jira")
    resolver = TrackerResolver({"jira": MockTrackerAdapter({"PROJ-1": {"key": "PROJ-1", "summary": "Title"}})})
    assert resolver.resolve(ref).status is ResolveStatus.RESOLVED
    assert resolver.load_summary(ref).summary == "Title"
    assert resolver.load_raw(ref)
    assert resolver.resolve(tracker_ref("issue", "MISSING", "jira")).status is ResolveStatus.UNRESOLVED
    assert TrackerResolver().resolve(ref).status is ResolveStatus.UNSUPPORTED
    broken = TrackerResolver({"jira": FailingAdapter()})
    assert broken.resolve(ref).status is ResolveStatus.UNRESOLVED
    assert not resolver.can_resolve("bad")


def test_memx_resolver_adapter_paths():
    evidence = memx_ref("evidence", "e1")
    resolver = MemxResolver(fetch_evidence=lambda ident: {"summary": f"Evidence {ident}"})
    assert resolver.resolve(evidence).status is ResolveStatus.RESOLVED
    assert resolver.load_summary(evidence).summary == "Evidence e1"
    assert resolver.load_raw(evidence)
    assert MemxResolver().resolve(evidence).status is ResolveStatus.UNSUPPORTED
    assert MemxResolver(fetch_evidence=lambda ident: None).resolve(evidence).status is ResolveStatus.UNRESOLVED
    assert MemxResolver(fetch_evidence=lambda ident: (_ for _ in ()).throw(RuntimeError("fetch failed"))).resolve(evidence).status is ResolveStatus.UNRESOLVED
    assert MemxResolver().resolve(memx_ref("unsupported", "x")).status is ResolveStatus.UNSUPPORTED
    assert not resolver.can_resolve("bad")


class FakeGithubIssue:
    title = "GitHub title"
    body = "Body"
    state = "open"
    html_url = "https://github/1"
    created_at = datetime(2026, 1, 1)
    updated_at = datetime(2026, 1, 2)
    assignee = SimpleNamespace(login="octocat")
    labels = [SimpleNamespace(name="bug")]
    comments = []
    edits = []

    def create_comment(self, comment):
        self.comments.append(comment)

    def edit(self, **kwargs):
        self.edits.append(kwargs)


class FakeGithubRepo:
    def __init__(self):
        self.issue = FakeGithubIssue()

    def get_issue(self, number):
        assert number == 7
        return self.issue


def test_github_adapter_with_fake_repository():
    adapter = GitHubAdapter("token", "owner", "repo")
    adapter._repo = FakeGithubRepo()
    raw = adapter.fetch_issue("#7")
    assert raw["number"] == 7
    assert adapter.parse_issue_key("owner/repo#8") == 8
    assert adapter.normalize_issue({"key": "x", "labels": "bug"})["labels"] == ["bug"]
    assert adapter.post_comment("7", "hello")
    assert adapter.update_status("7", "closed")
    assert adapter.update_status("7", "open")


class FakeJiraIssue:
    key = "PROJ-1"
    fields = SimpleNamespace(
        summary="Jira title",
        description="Description",
        status=SimpleNamespace(name="Open"),
        assignee=SimpleNamespace(displayName="User"),
        priority=SimpleNamespace(name="High"),
        labels=[SimpleNamespace(name="backend")],
        created=datetime(2026, 1, 1),
        updated=datetime(2026, 1, 2),
    )


class FakeJira:
    def __init__(self):
        self.comments = []
        self.transitions_called = []

    def issue(self, key):
        assert key == "PROJ-1"
        return FakeJiraIssue()

    def add_comment(self, issue, comment):
        self.comments.append(comment)

    def transitions(self, issue):
        return [{"name": "Done", "id": "31"}]

    def transition_issue(self, issue, ident):
        self.transitions_called.append((issue.key, ident))


def test_jira_adapter_with_fake_client():
    adapter = JiraAdapter("https://jira", "user", "password")
    adapter._jira = FakeJira()
    raw = adapter.fetch_issue("PROJ-1")
    assert raw["key"] == "PROJ-1"
    assert adapter.normalize_issue({"key": "x", "labels": "bug"})["labels"] == ["bug"]
    assert adapter.post_comment("PROJ-1", "hello")
    assert adapter.update_status("PROJ-1", "Done")
    assert not adapter.update_status("PROJ-1", "Missing")


def test_tracker_error_classification_and_missing_adapter(tmp_path):
    assert classify_adapter_exception(PermissionError("forbidden")) == "auth"
    assert classify_adapter_exception(LookupError("not found")) == "not-found"
    assert classify_adapter_exception(RuntimeError("rate limit 429")) == "rate-limit"
    assert classify_adapter_exception(ValueError("invalid value")) == "validation"
    assert classify_adapter_exception(RuntimeError("network")) == "transport"
    conn = sqlite3.connect(tmp_path / "tracker.db")
    conn.row_factory = sqlite3.Row
    create_tracker_tables(conn)
    service = TrackerBridgeService(conn)
    connection = service.create_connection("jira", "missing", {"url": "https://example.invalid"})
    assert service.fetch_issue(connection.id, "X") is None
    assert not service.post_outbound_comment(connection.id, "X", "comment")
    assert not service.update_outbound_status(connection.id, "X", "Done")
    with pytest.raises(ValueError):
        service.create_connection("jira", "bad", {}, {"token": 1})
    with pytest.raises(ValueError):
        service.link_issue_to_task("bad", "bad")
    conn.close()


def test_context_rebuild_latest_bundle_and_invalid_ref(tmp_path):
    conn = sqlite3.connect(tmp_path / "bundle.db")
    init_db(conn)
    now = "2026-01-01T00:00:00Z"
    conn.execute(
        "INSERT INTO tasks(id, kind, title, goal, status, priority, owner_type, created_at, updated_at) "
        "VALUES ('t1','feature','Bundle task','Goal','draft','medium','system',?,?)",
        (now, now),
    )
    conn.execute(
        "INSERT INTO task_states(task_id, revision, current_step, constraints_json, done_when_json, "
        "artifact_refs_json, evidence_refs_json, context_policy_json, confidence, created_at, updated_at) "
        "VALUES ('t1',1,'step','[]','[]','[\"invalid\"]','[]','{}','medium',?,?)",
        (now, now),
    )
    conn.commit()
    service = ContextRebuildService(conn)
    bundle = service.build("t1")
    assert bundle.id
    assert service.get_latest_bundle("t1").id == bundle.id
    service.clear_cache()
    assert service.get_latest_bundle("t1").id == bundle.id
    assert service.get_latest_bundle("missing") is None
    conn.close()

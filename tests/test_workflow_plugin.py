from __future__ import annotations

from pathlib import Path

from agent_taskstate_workflow_plugin.plugin import create_plugin
from agent_taskstate_workflow_plugin.results import AcceptanceIndexResult, TaskAcceptanceSyncResult
from agent_taskstate_workflow_plugin.store import MarkdownTaskAcceptanceStore


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def test_sync_task_acceptance_links_done_task_to_acceptance(tmp_path: Path) -> None:
    _write(
        tmp_path / "docs" / "tasks" / "task-sample.md",
        """
---
task_id: 20260410-01
intent_id: INT-001
owner: docs-core
status: done
---

# Task Seed: Sample
""",
    )
    _write(
        tmp_path / "docs" / "acceptance" / "AC-20260410-01.md",
        """
---
acceptance_id: AC-20260410-01
task_id: 20260410-01
intent_id: INT-001
owner: docs-core
status: approved
reviewed_at: 2026-04-10
reviewed_by: docs-core
---

# Acceptance Record
""",
    )

    plugin = create_plugin()
    report = plugin.sync_task_acceptance(repo_root=tmp_path)

    assert isinstance(report, TaskAcceptanceSyncResult)
    assert report.errors == []
    assert report.warnings == []
    assert report.tasks[0]["acceptance_ids"] == ["AC-20260410-01"]


def test_sync_task_acceptance_warns_for_done_task_without_acceptance_by_default(tmp_path: Path) -> None:
    _write(
        tmp_path / "docs" / "tasks" / "task-sample.md",
        """
---
task_id: 20260410-02
intent_id: INT-001
owner: docs-core
status: done
---

# Task Seed: Sample
""",
    )

    plugin = create_plugin()
    report = plugin.sync_task_acceptance(repo_root=tmp_path)

    assert report.errors == []
    assert report.warnings == ["Done task '20260410-02' is missing an acceptance record."]
    assert report.tasks[0]["acceptance_ids"] == []


def test_sync_task_acceptance_can_require_acceptance_for_done_tasks(tmp_path: Path) -> None:
    _write(
        tmp_path / "docs" / "tasks" / "task-sample.md",
        """
---
task_id: 20260410-03
intent_id: INT-001
owner: docs-core
status: done
---

# Task Seed: Sample
""",
    )

    plugin = create_plugin(require_acceptance_for_done=True)
    report = plugin.sync_task_acceptance(repo_root=tmp_path)

    assert report.errors == ["Done task '20260410-03' is missing an acceptance record."]
    assert report.warnings == []


def test_build_acceptance_index_renders_table(tmp_path: Path) -> None:
    _write(
        tmp_path / "docs" / "acceptance" / "AC-20260410-01.md",
        """
---
acceptance_id: AC-20260410-01
task_id: 20260410-01
intent_id: INT-001
owner: docs-core
status: approved
reviewed_at: 2026-04-10
reviewed_by: docs-core
---

# Acceptance Record
""",
    )

    plugin = create_plugin()
    payload = plugin.build_acceptance_index(repo_root=tmp_path)

    assert isinstance(payload, AcceptanceIndexResult)
    assert "| Acceptance | Task | Intent | Status | Reviewed | File |" in payload.markdown
    assert "AC-20260410-01" in payload.markdown


def test_markdown_task_acceptance_store_loads_task_and_acceptance(tmp_path: Path) -> None:
    _write(
        tmp_path / "docs" / "tasks" / "task-sample.md",
        """
---
task_id: 20260410-01
intent_id: INT-001
owner: docs-core
status: active
---

# Task Seed
""",
    )
    _write(
        tmp_path / "docs" / "acceptance" / "AC-20260410-01.md",
        """
---
acceptance_id: AC-20260410-01
task_id: 20260410-01
intent_id: INT-001
owner: docs-core
status: approved
reviewed_at: 2026-04-10
reviewed_by: docs-core
---

# Acceptance Record
""",
    )

    store = MarkdownTaskAcceptanceStore()

    tasks = store.load_tasks(repo_root=tmp_path)
    acceptances = store.load_acceptances(repo_root=tmp_path)

    assert tasks[0].task_id == "20260410-01"
    assert acceptances[0]["acceptance_id"] == "AC-20260410-01"

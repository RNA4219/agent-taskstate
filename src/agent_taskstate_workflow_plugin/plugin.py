from __future__ import annotations

from pathlib import Path

from agent_taskstate.typed_ref import agent_taskstate_ref
from .renderer import render_acceptance_index_markdown
from .results import AcceptanceIndexResult, TaskAcceptanceSyncResult
from .store import MarkdownTaskAcceptanceStore, TaskAcceptanceStore


class AgentTaskstateWorkflowPlugin:
    capabilities = ("task_state.sync", "acceptance.index")

    def __init__(
        self,
        *,
        tasks_dir: str = "docs/tasks",
        acceptance_dir: str = "docs/acceptance",
        require_acceptance_for_done: bool = False,
        store: TaskAcceptanceStore | None = None,
    ) -> None:
        self._require_acceptance_for_done = require_acceptance_for_done
        self._store = store or MarkdownTaskAcceptanceStore(
            tasks_dir=tasks_dir,
            acceptance_dir=acceptance_dir,
        )

    def sync_task_acceptance(self, *, repo_root: Path) -> TaskAcceptanceSyncResult:
        tasks = self._store.load_tasks(repo_root=repo_root)
        acceptances = self._store.load_acceptances(repo_root=repo_root)
        by_task: dict[str, list[dict]] = {}
        for acceptance in acceptances:
            by_task.setdefault(acceptance["task_id"], []).append(acceptance)

        errors: list[str] = []
        warnings: list[str] = []
        rendered_tasks: list[dict] = []
        for task in tasks:
            linked = by_task.get(task.task_id, [])
            acceptance_ids = [item["acceptance_id"] for item in linked]
            if task.status.lower() == "done" and not acceptance_ids:
                message = f"Done task '{task.task_id}' is missing an acceptance record."
                if self._require_acceptance_for_done:
                    errors.append(message)
                else:
                    warnings.append(message)
            for acceptance in linked:
                if acceptance["intent_id"] != task.intent_id:
                    errors.append(
                        f"Intent mismatch for task '{task.task_id}': task={task.intent_id} acceptance={acceptance['intent_id']}"
                    )
            rendered_tasks.append(
                {
                    "task_id": task.task_id,
                    "intent_id": task.intent_id,
                    "owner": task.owner,
                    "status": task.status,
                    "path": task.path,
                    "title": task.title,
                    "typed_ref": agent_taskstate_ref("task", task.task_id),
                    "acceptance_ids": acceptance_ids,
                }
            )

        known_task_ids = {task.task_id for task in tasks}
        for acceptance in acceptances:
            if acceptance["task_id"] not in known_task_ids:
                errors.append(
                    f"Acceptance '{acceptance['acceptance_id']}' references unknown task '{acceptance['task_id']}'."
                )

        return TaskAcceptanceSyncResult(
            tasks=rendered_tasks,
            acceptances=acceptances,
            errors=errors,
            warnings=warnings,
        )

    def build_acceptance_index(self, *, repo_root: Path) -> AcceptanceIndexResult:
        acceptances = sorted(
            self._store.load_acceptances(repo_root=repo_root),
            key=lambda item: (item["reviewed_at"], item["acceptance_id"]),
            reverse=True,
        )
        return AcceptanceIndexResult(
            markdown=render_acceptance_index_markdown(acceptances),
            rows=acceptances,
        )


def create_plugin(**kwargs: object) -> AgentTaskstateWorkflowPlugin:
    return AgentTaskstateWorkflowPlugin(**kwargs)

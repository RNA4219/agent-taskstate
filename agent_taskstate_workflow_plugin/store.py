from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from src.typed_ref import agent_taskstate_ref

from .markdown import read_markdown


@dataclass(frozen=True)
class TaskRecord:
    task_id: str
    intent_id: str
    owner: str
    status: str
    path: str
    title: str


class TaskAcceptanceStore(Protocol):
    def load_tasks(self, *, repo_root: Path) -> list[TaskRecord]:
        ...

    def load_acceptances(self, *, repo_root: Path) -> list[dict]:
        ...


class MarkdownTaskAcceptanceStore:
    def __init__(self, *, tasks_dir: str = "docs/tasks", acceptance_dir: str = "docs/acceptance") -> None:
        self._tasks_dir = tasks_dir
        self._acceptance_dir = acceptance_dir

    def load_tasks(self, *, repo_root: Path) -> list[TaskRecord]:
        tasks_root = repo_root / self._tasks_dir
        records: list[TaskRecord] = []
        for path in sorted(tasks_root.glob("*.md")):
            _, fields, title = read_markdown(path)
            task_id = fields.get("task_id", "").strip()
            if not task_id:
                continue
            records.append(
                TaskRecord(
                    task_id=task_id,
                    intent_id=fields.get("intent_id", ""),
                    owner=fields.get("owner", ""),
                    status=fields.get("status", ""),
                    path=path.relative_to(repo_root).as_posix(),
                    title=title,
                )
            )
        return records

    def load_acceptances(self, *, repo_root: Path) -> list[dict]:
        acceptance_root = repo_root / self._acceptance_dir
        items: list[dict] = []
        for path in sorted(acceptance_root.glob("AC-*.md")):
            _, fields, _ = read_markdown(path)
            if not fields.get("acceptance_id"):
                continue
            items.append(
                {
                    "acceptance_id": fields.get("acceptance_id", ""),
                    "task_id": fields.get("task_id", ""),
                    "intent_id": fields.get("intent_id", ""),
                    "status": fields.get("status", ""),
                    "reviewed_at": fields.get("reviewed_at", ""),
                    "reviewed_by": fields.get("reviewed_by", ""),
                    "path": path.relative_to(repo_root).as_posix(),
                    "typed_ref": agent_taskstate_ref("acceptance", fields.get("acceptance_id", "")),
                }
            )
        return items

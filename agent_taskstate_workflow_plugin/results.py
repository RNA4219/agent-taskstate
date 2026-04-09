from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TaskAcceptanceSyncResult:
    tasks: list[dict[str, Any]]
    acceptances: list[dict[str, Any]]
    errors: list[str]
    warnings: list[str]


@dataclass(frozen=True)
class AcceptanceIndexResult:
    markdown: str
    rows: list[dict[str, Any]]

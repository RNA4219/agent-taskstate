"""Configurable state transition rules."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "config" / "transitions.yaml"


@dataclass
class TransitionConfig:
    workflow: str = "default"
    statuses: Set[str] = field(
        default_factory=lambda: {
            "draft",
            "proposed",
            "ready",
            "in_progress",
            "blocked",
            "review",
            "done",
            "cancelled",
            "archived",
        }
    )
    terminal_states: Set[str] = field(default_factory=lambda: {"done", "cancelled", "archived"})
    allowed_transitions: Dict[str, Set[str]] = field(
        default_factory=lambda: {
            "draft": {"ready", "archived"},
            "proposed": {"ready", "cancelled"},
            "ready": {"in_progress", "cancelled"},
            "in_progress": {"blocked", "review", "cancelled"},
            "blocked": {"in_progress", "cancelled"},
            "review": {"in_progress", "done", "cancelled"},
            "done": {"in_progress", "archived"},
            "cancelled": set(),
            "archived": set(),
        }
    )
    reason_required: List[Dict[str, str]] = field(
        default_factory=lambda: [
            {"from": "done", "to": "in_progress"},
            {"from": "*", "to": "done"},
            {"from": "*", "to": "cancelled"},
            {"from": "*", "to": "archived"},
        ]
    )
    actor_types: Set[str] = field(default_factory=lambda: {"human", "agent", "system"})

    @classmethod
    def from_yaml(cls, path: Optional[Path] = None) -> "TransitionConfig":
        if yaml is None:
            return cls()
        config_path = path or DEFAULT_CONFIG_PATH
        if not config_path.exists():
            return cls()
        with config_path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
        return cls(
            workflow=data.get("workflow", "default"),
            statuses=set(data.get("statuses", cls().statuses)),
            terminal_states=set(data.get("terminal_states", cls().terminal_states)),
            allowed_transitions={
                status: set(trans.get("allowed", []))
                for status, trans in data.get("transitions", {}).items()
            }
            or cls().allowed_transitions,
            reason_required=data.get("reason_required", cls().reason_required),
            actor_types=set(data.get("actor_types", cls().actor_types)),
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TransitionConfig":
        defaults = cls()
        return cls(
            workflow=data.get("workflow", defaults.workflow),
            statuses=set(data.get("statuses", defaults.statuses)),
            terminal_states=set(data.get("terminal_states", defaults.terminal_states)),
            allowed_transitions={
                key: set(value)
                for key, value in data.get(
                    "allowed_transitions", defaults.allowed_transitions
                ).items()
            },
            reason_required=data.get("reason_required", defaults.reason_required),
            actor_types=set(data.get("actor_types", defaults.actor_types)),
        )

    def is_valid_status(self, status: str) -> bool:
        return status in self.statuses

    def can_transition(self, from_status: str, to_status: str) -> bool:
        return to_status in self.allowed_transitions.get(from_status, set())

    def is_terminal(self, status: str) -> bool:
        return status in self.terminal_states

    def requires_reason(self, from_status: str, to_status: str) -> bool:
        return any(
            (rule.get("from") in {"*", from_status}) and rule.get("to") == to_status
            for rule in self.reason_required
        )

    def is_valid_actor(self, actor_type: str) -> bool:
        return actor_type in self.actor_types


DEFAULT_CONFIG = TransitionConfig.from_yaml()


def get_config(path: Optional[Path] = None) -> TransitionConfig:
    return TransitionConfig.from_yaml(path) if path else DEFAULT_CONFIG


def reload_config(path: Optional[Path] = None) -> TransitionConfig:
    global DEFAULT_CONFIG
    DEFAULT_CONFIG = TransitionConfig.from_yaml(path)
    return DEFAULT_CONFIG

"""
State Transition Configuration Loader

Loads transition rules from YAML configuration files.
Allows workflow-specific customization of state transitions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "config" / "transitions.yaml"


@dataclass
class TransitionConfig:
    """Configuration for state transitions."""

    workflow: str = "default"
    statuses: Set[str] = field(default_factory=lambda: {
        "proposed", "ready", "in_progress", "blocked", "review", "done", "cancelled"
    })
    terminal_states: Set[str] = field(default_factory=lambda: {"done", "cancelled"})
    allowed_transitions: Dict[str, Set[str]] = field(default_factory=lambda: {
        "proposed": {"ready", "cancelled"},
        "ready": {"in_progress", "cancelled"},
        "in_progress": {"blocked", "review", "cancelled"},
        "blocked": {"in_progress", "cancelled"},
        "review": {"in_progress", "done", "cancelled"},
        "done": {"in_progress"},
        "cancelled": set(),
    })
    reason_required: List[Dict[str, str]] = field(default_factory=lambda: [
        {"from": "done", "to": "in_progress"},
        {"from": "*", "to": "done"},
        {"from": "*", "to": "cancelled"},
    ])
    actor_types: Set[str] = field(default_factory=lambda: {"human", "agent", "system"})

    @classmethod
    def from_yaml(cls, path: Optional[Path] = None) -> "TransitionConfig":
        """
        Load configuration from YAML file.

        Args:
            path: Path to YAML config file. Defaults to config/transitions.yaml

        Returns:
            TransitionConfig instance

        Raises:
            FileNotFoundError: If config file not found
            ValueError: If YAML parsing fails
        """
        if not YAML_AVAILABLE:
            # Fall back to default if yaml not installed
            return cls()

        config_path = path or DEFAULT_CONFIG_PATH
        if not config_path.exists():
            return cls()

        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not data:
            return cls()

        return cls(
            workflow=data.get("workflow", "default"),
            statuses=set(data.get("statuses", cls().statuses)),
            terminal_states=set(data.get("terminal_states", cls().terminal_states)),
            allowed_transitions={
                status: set(trans.get("allowed", []))
                for status, trans in data.get("transitions", {}).items()
            },
            reason_required=data.get("reason_required", []),
            actor_types=set(data.get("actor_types", cls().actor_types)),
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TransitionConfig":
        """
        Create configuration from dictionary.

        Args:
            data: Configuration dictionary

        Returns:
            TransitionConfig instance
        """
        return cls(
            workflow=data.get("workflow", "default"),
            statuses=set(data.get("statuses", cls().statuses)),
            terminal_states=set(data.get("terminal_states", cls().terminal_states)),
            allowed_transitions={
                k: set(v) if isinstance(v, list) else v
                for k, v in data.get("allowed_transitions", {}).items()
            },
            reason_required=data.get("reason_required", []),
            actor_types=set(data.get("actor_types", cls().actor_types)),
        )

    def is_valid_status(self, status: str) -> bool:
        """Check if status is valid."""
        return status in self.statuses

    def can_transition(self, from_status: str, to_status: str) -> bool:
        """Check if transition is allowed."""
        if from_status not in self.allowed_transitions:
            return False
        return to_status in self.allowed_transitions.get(from_status, set())

    def is_terminal(self, status: str) -> bool:
        """Check if status is terminal."""
        return status in self.terminal_states

    def requires_reason(self, from_status: str, to_status: str) -> bool:
        """
        Check if transition requires a reason.

        Based on reason_required configuration.
        """
        for rule in self.reason_required:
            rule_from = rule.get("from")
            rule_to = rule.get("to")

            # Wildcard matches any status
            from_match = rule_from == "*" or rule_from == from_status
            to_match = rule_to == to_status

            if from_match and to_match:
                return True

        return False

    def is_valid_actor(self, actor_type: str) -> bool:
        """Check if actor type is valid."""
        return actor_type in self.actor_types


# Global default configuration - loaded from YAML if available
DEFAULT_CONFIG = TransitionConfig.from_yaml()


def get_config(path: Optional[Path] = None) -> TransitionConfig:
    """
    Get transition configuration.

    Args:
        path: Optional path to YAML config file

    Returns:
        TransitionConfig instance
    """
    if path:
        return TransitionConfig.from_yaml(path)
    return DEFAULT_CONFIG


def reload_config(path: Optional[Path] = None) -> TransitionConfig:
    """
    Reload configuration from file.

    Args:
        path: Optional path to YAML config file

    Returns:
        New TransitionConfig instance
    """
    global DEFAULT_CONFIG
    DEFAULT_CONFIG = TransitionConfig.from_yaml(path)
    return DEFAULT_CONFIG
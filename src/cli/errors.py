"""
CLI Exception Classes
"""

from __future__ import annotations

from typing import Optional


class AgentTaskstateError(Exception):
    """Base error for agent-taskstate CLI."""
    code = "validation_error"

    def __init__(self, message: str, *, code: Optional[str] = None) -> None:
        super().__init__(message)
        if code:
            self.code = code


class NotFoundError(AgentTaskstateError):
    """Raised when a resource is not found."""
    code = "not_found"


class ConflictError(AgentTaskstateError):
    """Raised when there is a conflict (e.g., revision mismatch)."""
    code = "conflict"


class InvalidTransitionError(AgentTaskstateError):
    """Raised when a status transition is invalid."""
    code = "invalid_transition"


class DependencyBlockedError(AgentTaskstateError):
    """Raised when a dependency blocks the operation."""
    code = "dependency_blocked"
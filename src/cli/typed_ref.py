"""
CLI Typed Reference Utilities

Format: <domain>:<entity_type>:<provider>:<entity_id>
"""

from __future__ import annotations

DEFAULT_PROVIDER = "local"


def typed_ref(
    domain: str,
    entity_type: str,
    entity_id: str,
    provider: str = DEFAULT_PROVIDER,
) -> str:
    """Generate 4-segment typed_ref."""
    return f"{domain}:{entity_type}:{provider}:{entity_id}"


def task_ref(task_id: str) -> str:
    """Generate task typed_ref."""
    return typed_ref("agent-taskstate", "task", task_id)


def decision_ref(decision_id: str) -> str:
    """Generate decision typed_ref."""
    return typed_ref("agent-taskstate", "decision", decision_id)


def question_ref(question_id: str) -> str:
    """Generate question typed_ref."""
    return typed_ref("agent-taskstate", "question", question_id)


def run_ref(run_id: str) -> str:
    """Generate run typed_ref."""
    return typed_ref("agent-taskstate", "run", run_id)


def bundle_ref(bundle_id: str) -> str:
    """Generate context_bundle typed_ref."""
    return typed_ref("agent-taskstate", "context_bundle", bundle_id)
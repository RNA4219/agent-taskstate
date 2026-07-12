"""Compatibility helpers backed by the canonical typed_ref module."""

from __future__ import annotations

from ..typed_ref import DEFAULT_PROVIDER, agent_taskstate_ref, format_ref


def typed_ref(
    domain: str,
    entity_type: str,
    entity_id: str,
    provider: str = DEFAULT_PROVIDER,
) -> str:
    """Deprecated helper that delegates to canonical format_ref."""
    return format_ref(domain, entity_type, entity_id, provider)


def task_ref(task_id: str) -> str:
    return agent_taskstate_ref("task", task_id)


def decision_ref(decision_id: str) -> str:
    return agent_taskstate_ref("decision", decision_id)


def question_ref(question_id: str) -> str:
    return agent_taskstate_ref("question", question_id)


def run_ref(run_id: str) -> str:
    return agent_taskstate_ref("run", run_id)


def bundle_ref(bundle_id: str) -> str:
    return agent_taskstate_ref("context_bundle", bundle_id)


__all__ = [
    "DEFAULT_PROVIDER",
    "typed_ref",
    "task_ref",
    "decision_ref",
    "question_ref",
    "run_ref",
    "bundle_ref",
]

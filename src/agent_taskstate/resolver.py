"""Typed-reference context rebuild resolvers."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Protocol

from .typed_ref import canonicalize_ref, parse_ref


class ResolveStatus(Enum):
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"
    UNSUPPORTED = "unsupported"


@dataclass
class ResolvedRef:
    ref: str
    status: ResolveStatus
    summary: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    raw_available: bool = False
    error_message: Optional[str] = None


@dataclass
class ResolveReport:
    resolved: List[ResolvedRef] = field(default_factory=list)
    unresolved: List[ResolvedRef] = field(default_factory=list)
    unsupported: List[ResolvedRef] = field(default_factory=list)

    @property
    def total_count(self) -> int:
        return len(self.resolved) + len(self.unresolved) + len(self.unsupported)

    @property
    def success_rate(self) -> float:
        return len(self.resolved) / self.total_count if self.total_count else 1.0


@dataclass
class SummaryPayload:
    ref: str
    summary: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RawPayload:
    ref: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ResolverDiagnostics:
    missing_refs: List[str] = field(default_factory=list)
    unsupported_refs: List[str] = field(default_factory=list)
    resolver_warnings: List[str] = field(default_factory=list)
    partial_bundle: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "missing_refs": self.missing_refs,
            "unsupported_refs": self.unsupported_refs,
            "resolver_warnings": self.resolver_warnings,
            "partial_bundle": self.partial_bundle,
        }


RAW_DESCENT_CONDITIONS = {
    "before_review",
    "conflicting_summaries",
    "high_priority_open_question",
    "low_confidence_decision",
    "investigation_step",
    "verification_step",
    "operator_request",
}


class RefResolver(Protocol):
    def can_resolve(self, ref: str) -> bool: ...
    def resolve(self, ref: str) -> ResolvedRef: ...
    def load_summary(self, ref: str) -> Optional[SummaryPayload]: ...
    def load_raw(
        self, ref: str, selector: Optional[Dict[str, Any]] = None
    ) -> Optional[RawPayload]: ...


class ContextRebuildResolver:
    def __init__(self) -> None:
        self._resolvers: List[RefResolver] = []

    def register_resolver(self, resolver: RefResolver) -> None:
        self._resolvers.append(resolver)

    def resolve_ref(self, ref: str) -> ResolvedRef:
        try:
            canonical = canonicalize_ref(ref)
            parsed = parse_ref(canonical)
        except ValueError as exc:
            return ResolvedRef(ref=ref, status=ResolveStatus.UNSUPPORTED, error_message=str(exc))
        for resolver in self._resolvers:
            if resolver.can_resolve(canonical):
                try:
                    result = resolver.resolve(canonical)
                except Exception as exc:  # diagnostics are part of the contract
                    return ResolvedRef(
                        ref=canonical,
                        status=ResolveStatus.UNRESOLVED,
                        error_message=f"{type(exc).__name__}: {exc}",
                    )
                result.ref = canonical
                return result
        return ResolvedRef(
            ref=canonical,
            status=ResolveStatus.UNSUPPORTED,
            error_message=f"No resolver for domain: {parsed.domain}",
        )

    def resolve_many(self, refs: List[str]) -> ResolveReport:
        report = ResolveReport()
        for ref in refs:
            result = self.resolve_ref(ref)
            if result.status is ResolveStatus.RESOLVED:
                report.resolved.append(result)
            elif result.status is ResolveStatus.UNRESOLVED:
                report.unresolved.append(result)
            else:
                report.unsupported.append(result)
        return report

    def load_summary(self, ref: str) -> Optional[SummaryPayload]:
        result = self.resolve_ref(ref)
        if result.status is ResolveStatus.RESOLVED and result.summary is not None:
            return SummaryPayload(result.ref, result.summary, result.metadata or {})
        return None

    def load_selected_raw(
        self, ref: str, selector: Optional[Dict[str, Any]] = None
    ) -> Optional[RawPayload]:
        canonical = canonicalize_ref(ref)
        for resolver in self._resolvers:
            if resolver.can_resolve(canonical):
                try:
                    return resolver.load_raw(canonical, selector)
                except Exception:
                    return None
        return None

    def should_include_raw(
        self, condition: str, task_context: Optional[Dict[str, Any]] = None
    ) -> bool:
        if condition not in RAW_DESCENT_CONDITIONS:
            return False
        if condition == "operator_request":
            return True
        if task_context and condition == "high_priority_open_question":
            return bool(task_context.get("has_high_priority_questions"))
        if task_context and condition == "low_confidence_decision":
            return bool(task_context.get("has_low_confidence_decisions"))
        return True

    def get_diagnostics(self, report: ResolveReport) -> ResolverDiagnostics:
        diagnostics = ResolverDiagnostics()
        for item in report.unresolved:
            diagnostics.missing_refs.append(item.ref)
            if item.error_message:
                diagnostics.resolver_warnings.append(f"{item.ref}: {item.error_message}")
        for item in report.unsupported:
            diagnostics.unsupported_refs.append(item.ref)
            if item.error_message:
                diagnostics.resolver_warnings.append(f"{item.ref}: {item.error_message}")
        diagnostics.partial_bundle = bool(report.unresolved or report.unsupported)
        return diagnostics


def _has_table(conn: Any, name: str) -> bool:
    return bool(
        conn
        and conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone()
    )


class AgentTaskstateLocalResolver:
    """Resolve local task, decision, question, run, and bundle refs."""

    def __init__(self, conn: Any = None):
        self.conn = conn

    def can_resolve(self, ref: str) -> bool:
        try:
            p = parse_ref(ref)
            return p.domain == "agent-taskstate" and p.provider == "local"
        except ValueError:
            return False

    def resolve(self, ref: str) -> ResolvedRef:
        p = parse_ref(ref)
        if self.conn is None:
            return ResolvedRef(
                ref=ref, status=ResolveStatus.UNRESOLVED, error_message="No database connection"
            )
        table_map = {
            "task": ("tasks", "title", "status"),
            "decision": ("decisions", "summary", "status"),
            "question": ("open_questions", "question", "status"),
            "run": ("runs", "run_type", "status"),
            "context_bundle": ("context_bundles", "summary", "purpose"),
        }
        entity = table_map.get(p.entity_type)
        if entity is None:
            return ResolvedRef(
                ref=ref,
                status=ResolveStatus.UNSUPPORTED,
                error_message=f"Unknown entity type: {p.entity_type}",
            )
        table, summary_col, status_col = entity
        if not _has_table(self.conn, table):
            legacy = {
                "tasks": "task",
                "decisions": "decision",
                "open_questions": "open_question",
                "runs": "run",
                "context_bundles": "context_bundle",
            }[table]
            table = legacy
        row = self.conn.execute(
            f"SELECT * FROM {table} WHERE id = ?"
            if p.entity_type != "task"
            else f"SELECT * FROM {table} WHERE id = ?",
            (p.entity_id,),
        ).fetchone()
        if not row:
            return ResolvedRef(
                ref=ref,
                status=ResolveStatus.UNRESOLVED,
                error_message=f"{p.entity_type} not found: {p.entity_id}",
            )
        keys = set(row.keys()) if hasattr(row, "keys") else set()
        summary = row[summary_col] if summary_col in keys else row[summary_col]
        status = row[status_col] if status_col in keys else None
        return ResolvedRef(
            ref=ref,
            status=ResolveStatus.RESOLVED,
            summary=summary or p.entity_type,
            metadata={"status": status} if status is not None else {},
            raw_available=True,
        )

    def load_summary(self, ref: str) -> Optional[SummaryPayload]:
        result = self.resolve(ref)
        return (
            SummaryPayload(result.ref, result.summary, result.metadata or {})
            if result.status is ResolveStatus.RESOLVED and result.summary
            else None
        )

    def load_raw(self, ref: str, selector: Optional[Dict[str, Any]] = None) -> Optional[RawPayload]:
        result = self.resolve(ref)
        if result.status is not ResolveStatus.RESOLVED:
            return None
        return RawPayload(result.ref, result.summary or "", result.metadata or {})


class TrackerResolver:
    def __init__(self, adapters: Optional[Dict[str, Any]] = None):
        self._adapters = adapters or {}

    def register_adapter(self, provider: str, adapter: Any) -> None:
        self._adapters[provider] = adapter

    def can_resolve(self, ref: str) -> bool:
        try:
            p = parse_ref(ref)
            return p.domain == "tracker" and p.entity_type == "issue"
        except ValueError:
            return False

    def resolve(self, ref: str) -> ResolvedRef:
        p = parse_ref(ref)
        adapter = self._adapters.get(p.provider)
        if adapter is None:
            return ResolvedRef(
                ref=ref,
                status=ResolveStatus.UNSUPPORTED,
                error_message=f"No adapter for tracker provider: {p.provider}",
            )
        try:
            raw = adapter.fetch_issue(p.entity_id)
            if not raw:
                return ResolvedRef(
                    ref=ref,
                    status=ResolveStatus.UNRESOLVED,
                    error_message=f"Issue not found: {p.entity_id}",
                )
            normalized = adapter.normalize_issue(raw)
            return ResolvedRef(
                ref=ref,
                status=ResolveStatus.RESOLVED,
                summary=normalized.get("title", ""),
                metadata=normalized,
                raw_available=True,
            )
        except Exception as exc:
            return ResolvedRef(
                ref=ref,
                status=ResolveStatus.UNRESOLVED,
                error_message=f"{type(exc).__name__}: {exc}",
            )

    def load_summary(self, ref: str) -> Optional[SummaryPayload]:
        result = self.resolve(ref)
        return (
            SummaryPayload(result.ref, result.summary, result.metadata or {})
            if result.status is ResolveStatus.RESOLVED and result.summary
            else None
        )

    def load_raw(self, ref: str, selector: Optional[Dict[str, Any]] = None) -> Optional[RawPayload]:
        p = parse_ref(ref)
        adapter = self._adapters.get(p.provider)
        if adapter is None:
            return None
        raw = adapter.fetch_issue(p.entity_id)
        return (
            RawPayload(ref, json.dumps(raw, ensure_ascii=False), {"provider": p.provider})
            if raw
            else None
        )


class MemxResolver:
    def __init__(
        self,
        fetch_evidence: Optional[Callable[[str], Optional[Dict[str, Any]]]] = None,
        fetch_knowledge: Optional[Callable[[str], Optional[Dict[str, Any]]]] = None,
        fetch_chunk: Optional[Callable[[str], Optional[Dict[str, Any]]]] = None,
    ):
        self._fetchers = {
            "evidence": fetch_evidence,
            "knowledge": fetch_knowledge,
            "chunk": fetch_chunk,
        }

    def can_resolve(self, ref: str) -> bool:
        try:
            return parse_ref(ref).domain == "memx"
        except ValueError:
            return False

    def resolve(self, ref: str) -> ResolvedRef:
        p = parse_ref(ref)
        fetcher = self._fetchers.get(p.entity_type)
        if fetcher is None:
            return ResolvedRef(
                ref=ref,
                status=ResolveStatus.UNSUPPORTED,
                error_message=f"Unsupported memx entity type: {p.entity_type}",
            )
        if fetcher is None:
            return ResolvedRef(
                ref=ref,
                status=ResolveStatus.UNSUPPORTED,
                error_message="memx adapter is not configured",
            )
        try:
            data = fetcher(p.entity_id)
        except Exception as exc:
            return ResolvedRef(
                ref=ref,
                status=ResolveStatus.UNRESOLVED,
                error_message=f"{type(exc).__name__}: {exc}",
            )
        if not data:
            return ResolvedRef(
                ref=ref,
                status=ResolveStatus.UNRESOLVED,
                error_message=f"{p.entity_type} not found: {p.entity_id}",
            )
        return ResolvedRef(
            ref=ref,
            status=ResolveStatus.RESOLVED,
            summary=data.get("summary", data.get("title", "")),
            metadata=data,
            raw_available=True,
        )

    def load_summary(self, ref: str) -> Optional[SummaryPayload]:
        result = self.resolve(ref)
        return (
            SummaryPayload(result.ref, result.summary, result.metadata or {})
            if result.status is ResolveStatus.RESOLVED and result.summary
            else None
        )

    def load_raw(self, ref: str, selector: Optional[Dict[str, Any]] = None) -> Optional[RawPayload]:
        p = parse_ref(ref)
        fetcher = self._fetchers.get(p.entity_type)
        if fetcher is None:
            return None
        data = fetcher(p.entity_id)
        return (
            RawPayload(ref, json.dumps(data, ensure_ascii=False), {"entity_type": p.entity_type})
            if data
            else None
        )

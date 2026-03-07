"""
Context Rebuild Resolver

Resolves typed_refs for context bundle building.
Implements summary-first retrieval with diagnostics.

Interface:
- ResolveRef(ref) -> ResolvedRef
- ResolveMany(refs) -> ResolveReport
- LoadSummary(ref) -> SummaryPayload
- LoadSelectedRaw(ref, selector) -> RawPayload
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol, Set


class ResolveStatus(Enum):
    """Status of ref resolution."""
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"
    UNSUPPORTED = "unsupported"


@dataclass
class ResolvedRef:
    """Result of resolving a single typed_ref."""
    ref: str
    status: ResolveStatus
    summary: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    raw_available: bool = False
    error_message: Optional[str] = None


@dataclass
class ResolveReport:
    """Report of resolving multiple refs."""
    resolved: List[ResolvedRef] = field(default_factory=list)
    unresolved: List[ResolvedRef] = field(default_factory=list)
    unsupported: List[ResolvedRef] = field(default_factory=list)

    @property
    def total_count(self) -> int:
        return len(self.resolved) + len(self.unresolved) + len(self.unsupported)

    @property
    def success_rate(self) -> float:
        if self.total_count == 0:
            return 1.0
        return len(self.resolved) / self.total_count


@dataclass
class SummaryPayload:
    """Summary content for a resolved ref."""
    ref: str
    summary: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RawPayload:
    """Raw content for a resolved ref."""
    ref: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ResolverDiagnostics:
    """Diagnostics for bundle build."""
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


# Conditions for raw descent
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
    """Protocol for ref resolvers."""

    def can_resolve(self, ref: str) -> bool:
        """Check if this resolver can handle the ref."""
        ...

    def resolve(self, ref: str) -> ResolvedRef:
        """Resolve a single ref."""
        ...

    def load_summary(self, ref: str) -> Optional[SummaryPayload]:
        """Load summary for a resolved ref."""
        ...

    def load_raw(self, ref: str, selector: Optional[Dict[str, Any]] = None) -> Optional[RawPayload]:
        """Load raw content for a resolved ref."""
        ...


class ContextRebuildResolver:
    """
    Main resolver for context rebuild.

    Coordinates multiple domain-specific resolvers and provides
    summary-first retrieval with diagnostics.
    """

    def __init__(self):
        self._resolvers: List[RefResolver] = []
        self._unsupported_domains: Set[str] = set()

    def register_resolver(self, resolver: RefResolver) -> None:
        """Register a domain-specific resolver."""
        self._resolvers.append(resolver)

    def resolve_ref(self, ref: str) -> ResolvedRef:
        """
        Resolve a single typed_ref.

        Args:
            ref: typed_ref string

        Returns:
            ResolvedRef with status and metadata
        """
        for resolver in self._resolvers:
            if resolver.can_resolve(ref):
                return resolver.resolve(ref)

        # No resolver found
        from .typed_ref import parse_ref
        try:
            parsed = parse_ref(ref)
            return ResolvedRef(
                ref=ref,
                status=ResolveStatus.UNSUPPORTED,
                error_message=f"No resolver for domain: {parsed.domain}",
            )
        except ValueError as e:
            return ResolvedRef(
                ref=ref,
                status=ResolveStatus.UNSUPPORTED,
                error_message=str(e),
            )

    def resolve_many(self, refs: List[str]) -> ResolveReport:
        """
        Resolve multiple refs.

        Args:
            refs: List of typed_ref strings

        Returns:
            ResolveReport with categorized results
        """
        report = ResolveReport()

        for ref in refs:
            result = self.resolve_ref(ref)

            if result.status == ResolveStatus.RESOLVED:
                report.resolved.append(result)
            elif result.status == ResolveStatus.UNRESOLVED:
                report.unresolved.append(result)
            else:
                report.unsupported.append(result)

        return report

    def load_summary(self, ref: str) -> Optional[SummaryPayload]:
        """
        Load summary for a ref (summary-first retrieval).

        Args:
            ref: typed_ref string

        Returns:
            SummaryPayload or None
        """
        for resolver in self._resolvers:
            if resolver.can_resolve(ref):
                return resolver.load_summary(ref)
        return None

    def load_selected_raw(
        self,
        ref: str,
        selector: Optional[Dict[str, Any]] = None
    ) -> Optional[RawPayload]:
        """
        Load raw content for a ref (selected raw inclusion).

        Args:
            ref: typed_ref string
            selector: Optional selector for partial raw

        Returns:
            RawPayload or None
        """
        for resolver in self._resolvers:
            if resolver.can_resolve(ref):
                return resolver.load_raw(ref, selector)
        return None

    def should_include_raw(
        self,
        condition: str,
        task_context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Determine if raw content should be included.

        Args:
            condition: Condition key (e.g., "before_review")
            task_context: Optional task context for decision

        Returns:
            True if raw should be included
        """
        if condition not in RAW_DESCENT_CONDITIONS:
            return False

        # Always include for operator request
        if condition == "operator_request":
            return True

        # Check task context for other conditions
        if task_context:
            if condition == "high_priority_open_question":
                return task_context.get("has_high_priority_questions", False)
            if condition == "low_confidence_decision":
                return task_context.get("has_low_confidence_decisions", False)

        return True

    def get_diagnostics(self, report: ResolveReport) -> ResolverDiagnostics:
        """
        Generate diagnostics from resolve report.

        Args:
            report: ResolveReport from resolve_many

        Returns:
            ResolverDiagnostics
        """
        diagnostics = ResolverDiagnostics()

        for ref in report.unresolved:
            diagnostics.missing_refs.append(ref.ref)
            diagnostics.resolver_warnings.append(
                f"Unresolved ref: {ref.ref} - {ref.error_message}"
            )

        for ref in report.unsupported:
            diagnostics.unsupported_refs.append(ref.ref)

        diagnostics.partial_bundle = (
            len(report.unresolved) > 0 or len(report.unsupported) > 0
        )

        return diagnostics


# Built-in resolver for workx entities (local)

class WorkxLocalResolver:
    """
    Resolver for workx local entities.
    Resolves refs like workx:task:local:*, workx:decision:local:*, etc.
    """

    def __init__(self, conn=None):
        self.conn = conn

    def can_resolve(self, ref: str) -> bool:
        """Check if this is a workx local ref."""
        from .typed_ref import parse_ref
        try:
            parsed = parse_ref(ref)
            return parsed.domain == "workx" and parsed.provider == "local"
        except ValueError:
            return False

    def resolve(self, ref: str) -> ResolvedRef:
        """Resolve a workx local ref."""
        from .typed_ref import parse_ref
        try:
            parsed = parse_ref(ref)

            # If no DB connection, return unresolved
            if self.conn is None:
                return ResolvedRef(
                    ref=ref,
                    status=ResolveStatus.UNRESOLVED,
                    error_message="No database connection",
                )

            # Check entity type
            entity_type = parsed.entity_type
            entity_id = parsed.entity_id

            if entity_type == "task":
                return self._resolve_task(entity_id)
            elif entity_type == "decision":
                return self._resolve_decision(entity_id)
            elif entity_type == "context_bundle":
                return self._resolve_bundle(entity_id)
            else:
                return ResolvedRef(
                    ref=ref,
                    status=ResolveStatus.UNRESOLVED,
                    error_message=f"Unknown entity type: {entity_type}",
                )

        except ValueError as e:
            return ResolvedRef(
                ref=ref,
                status=ResolveStatus.UNSUPPORTED,
                error_message=str(e),
            )

    def _resolve_task(self, task_id: str) -> ResolvedRef:
        """Resolve a task."""
        cursor = self.conn.execute(
            "SELECT id, title, status FROM task WHERE id = ?",
            (task_id,),
        )
        row = cursor.fetchone()

        if row:
            return ResolvedRef(
                ref=f"workx:task:local:{task_id}",
                status=ResolveStatus.RESOLVED,
                summary=row["title"],
                metadata={"status": row["status"]},
                raw_available=True,
            )
        else:
            return ResolvedRef(
                ref=f"workx:task:local:{task_id}",
                status=ResolveStatus.UNRESOLVED,
                error_message=f"Task not found: {task_id}",
            )

    def _resolve_decision(self, decision_id: str) -> ResolvedRef:
        """Resolve a decision."""
        cursor = self.conn.execute(
            "SELECT id, summary, status FROM decision WHERE id = ?",
            (decision_id,),
        )
        row = cursor.fetchone()

        if row:
            return ResolvedRef(
                ref=f"workx:decision:local:{decision_id}",
                status=ResolveStatus.RESOLVED,
                summary=row["summary"],
                metadata={"status": row["status"]},
                raw_available=True,
            )
        else:
            return ResolvedRef(
                ref=f"workx:decision:local:{decision_id}",
                status=ResolveStatus.UNRESOLVED,
                error_message=f"Decision not found: {decision_id}",
            )

    def _resolve_bundle(self, bundle_id: str) -> ResolvedRef:
        """Resolve a context bundle."""
        cursor = self.conn.execute(
            "SELECT id, purpose, summary FROM context_bundle WHERE id = ?",
            (bundle_id,),
        )
        row = cursor.fetchone()

        if row:
            return ResolvedRef(
                ref=f"workx:context_bundle:local:{bundle_id}",
                status=ResolveStatus.RESOLVED,
                summary=row["summary"] or row["purpose"],
                metadata={"purpose": row["purpose"]},
                raw_available=True,
            )
        else:
            return ResolvedRef(
                ref=f"workx:context_bundle:local:{bundle_id}",
                status=ResolveStatus.UNRESOLVED,
                error_message=f"Bundle not found: {bundle_id}",
            )

    def load_summary(self, ref: str) -> Optional[SummaryPayload]:
        """Load summary for a workx ref."""
        result = self.resolve(ref)
        if result.status == ResolveStatus.RESOLVED and result.summary:
            return SummaryPayload(
                ref=ref,
                summary=result.summary,
                metadata=result.metadata or {},
            )
        return None

    def load_raw(self, ref: str, selector: Optional[Dict[str, Any]] = None) -> Optional[RawPayload]:
        """Load raw content for a workx ref."""
        # For workx entities, summary is typically sufficient
        summary = self.load_summary(ref)
        if summary:
            return RawPayload(
                ref=ref,
                content=summary.summary,
                metadata=summary.metadata,
            )
        return None
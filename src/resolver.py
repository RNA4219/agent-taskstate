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


# Built-in resolver for agent-taskstate entities (local)

class AgentTaskstateLocalResolver:
    """
    Resolver for agent-taskstate local entities.
    Resolves refs like agent-taskstate:task:local:*, agent-taskstate:decision:local:*, etc.
    """

    def __init__(self, conn=None):
        self.conn = conn

    def can_resolve(self, ref: str) -> bool:
        """Check if this is an agent-taskstate local ref."""
        from .typed_ref import parse_ref
        try:
            parsed = parse_ref(ref)
            return parsed.domain == "agent-taskstate" and parsed.provider == "local"
        except ValueError:
            return False

    def resolve(self, ref: str) -> ResolvedRef:
        """Resolve an agent-taskstate local ref."""
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
                ref=f"agent-taskstate:task:local:{task_id}",
                status=ResolveStatus.RESOLVED,
                summary=row["title"],
                metadata={"status": row["status"]},
                raw_available=True,
            )
        else:
            return ResolvedRef(
                ref=f"agent-taskstate:task:local:{task_id}",
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
                ref=f"agent-taskstate:decision:local:{decision_id}",
                status=ResolveStatus.RESOLVED,
                summary=row["summary"],
                metadata={"status": row["status"]},
                raw_available=True,
            )
        else:
            return ResolvedRef(
                ref=f"agent-taskstate:decision:local:{decision_id}",
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
                ref=f"agent-taskstate:context_bundle:local:{bundle_id}",
                status=ResolveStatus.RESOLVED,
                summary=row["summary"] or row["purpose"],
                metadata={"purpose": row["purpose"]},
                raw_available=True,
            )
        else:
            return ResolvedRef(
                ref=f"agent-taskstate:context_bundle:local:{bundle_id}",
                status=ResolveStatus.UNRESOLVED,
                error_message=f"Bundle not found: {bundle_id}",
            )

    def load_summary(self, ref: str) -> Optional[SummaryPayload]:
        """Load summary for an agent-taskstate ref."""
        result = self.resolve(ref)
        if result.status == ResolveStatus.RESOLVED and result.summary:
            return SummaryPayload(
                ref=ref,
                summary=result.summary,
                metadata=result.metadata or {},
            )
        return None

    def load_raw(self, ref: str, selector: Optional[Dict[str, Any]] = None) -> Optional[RawPayload]:
        """Load raw content for an agent-taskstate ref."""
        # For agent-taskstate entities, summary is typically sufficient
        summary = self.load_summary(ref)
        if summary:
            return RawPayload(
                ref=ref,
                content=summary.summary,
                metadata=summary.metadata,
            )
        return None


class TrackerResolver:
    """
    Resolver for tracker issue refs.

    Resolves refs like tracker:issue:github:owner/repo#123, tracker:issue:jira:PROJ-123

    Uses TrackerAdapter for actual fetch operations.
    """

    def __init__(self, adapters: Optional[Dict[str, "TrackerAdapter"]] = None):
        """
        Initialize with provider-specific adapters.

        Args:
            adapters: Dict mapping provider name to TrackerAdapter instance
        """
        self._adapters = adapters or {}

    def register_adapter(self, provider: str, adapter: "TrackerAdapter") -> None:
        """Register adapter for a provider."""
        self._adapters[provider] = adapter

    def can_resolve(self, ref: str) -> bool:
        """Check if this is a tracker issue ref."""
        from .typed_ref import parse_ref
        try:
            parsed = parse_ref(ref)
            return parsed.domain == "tracker" and parsed.entity_type == "issue"
        except ValueError:
            return False

    def resolve(self, ref: str) -> ResolvedRef:
        """Resolve a tracker issue ref."""
        from .typed_ref import parse_ref
        try:
            parsed = parse_ref(ref)
            provider = parsed.provider
            issue_key = parsed.entity_id

            adapter = self._adapters.get(provider)
            if not adapter:
                return ResolvedRef(
                    ref=ref,
                    status=ResolveStatus.UNSUPPORTED,
                    error_message=f"No adapter for tracker provider: {provider}",
                )

            raw = adapter.fetch_issue(issue_key)
            if not raw:
                return ResolvedRef(
                    ref=ref,
                    status=ResolveStatus.UNRESOLVED,
                    error_message=f"Issue not found: {issue_key}",
                )

            normalized = adapter.normalize_issue(raw)
            return ResolvedRef(
                ref=ref,
                status=ResolveStatus.RESOLVED,
                summary=normalized.get("title", ""),
                metadata={
                    "remote_key": normalized.get("remote_key"),
                    "status": normalized.get("status"),
                    "assignee": normalized.get("assignee"),
                },
                raw_available=True,
            )

        except ValueError as e:
            return ResolvedRef(
                ref=ref,
                status=ResolveStatus.UNSUPPORTED,
                error_message=str(e),
            )

    def load_summary(self, ref: str) -> Optional[SummaryPayload]:
        """Load summary for a tracker issue."""
        result = self.resolve(ref)
        if result.status == ResolveStatus.RESOLVED and result.summary:
            return SummaryPayload(
                ref=ref,
                summary=result.summary,
                metadata=result.metadata or {},
            )
        return None

    def load_raw(self, ref: str, selector: Optional[Dict[str, Any]] = None) -> Optional[RawPayload]:
        """Load raw content for a tracker issue."""
        from .typed_ref import parse_ref
        try:
            parsed = parse_ref(ref)
            adapter = self._adapters.get(parsed.provider)
            if not adapter:
                return None

            raw = adapter.fetch_issue(parsed.entity_id)
            if not raw:
                return None

            import json
            return RawPayload(
                ref=ref,
                content=json.dumps(raw, ensure_ascii=False),
                metadata={"provider": parsed.provider},
            )
        except Exception:
            return None


class MemxResolver:
    """
    Resolver for memx entity refs.

    Resolves refs like memx:evidence:local:ev_01JXYZ..., memx:knowledge:local:kn_01JXYZ...

    Designed for integration with memx-resolver repo.
    Uses callback functions for actual fetch operations.
    """

    def __init__(
        self,
        fetch_evidence: Optional[callable] = None,
        fetch_knowledge: Optional[callable] = None,
        fetch_chunk: Optional[callable] = None,
    ):
        """
        Initialize with fetch callbacks.

        Args:
            fetch_evidence: Callable to fetch evidence by ID
            fetch_knowledge: Callable to fetch knowledge by ID
            fetch_chunk: Callable to fetch chunk by ID
        """
        self._fetch_evidence = fetch_evidence
        self._fetch_knowledge = fetch_knowledge
        self._fetch_chunk = fetch_chunk

    def can_resolve(self, ref: str) -> bool:
        """Check if this is a memx ref."""
        from .typed_ref import parse_ref
        try:
            parsed = parse_ref(ref)
            return parsed.domain == "memx"
        except ValueError:
            return False

    def resolve(self, ref: str) -> ResolvedRef:
        """Resolve a memx entity ref."""
        from .typed_ref import parse_ref
        try:
            parsed = parse_ref(ref)
            entity_type = parsed.entity_type
            entity_id = parsed.entity_id

            if entity_type == "evidence":
                return self._resolve_evidence(entity_id)
            elif entity_type == "knowledge":
                return self._resolve_knowledge(entity_id)
            elif entity_type == "chunk":
                return self._resolve_chunk(entity_id)
            else:
                return ResolvedRef(
                    ref=ref,
                    status=ResolveStatus.UNSUPPORTED,
                    error_message=f"Unknown memx entity type: {entity_type}",
                )

        except ValueError as e:
            return ResolvedRef(
                ref=ref,
                status=ResolveStatus.UNSUPPORTED,
                error_message=str(e),
            )

    def _resolve_evidence(self, evidence_id: str) -> ResolvedRef:
        """Resolve evidence entity."""
        if not self._fetch_evidence:
            return ResolvedRef(
                ref=f"memx:evidence:local:{evidence_id}",
                status=ResolveStatus.UNRESOLVED,
                error_message="No evidence fetch callback configured",
            )

        try:
            data = self._fetch_evidence(evidence_id)
            if not data:
                return ResolvedRef(
                    ref=f"memx:evidence:local:{evidence_id}",
                    status=ResolveStatus.UNRESOLVED,
                    error_message=f"Evidence not found: {evidence_id}",
                )

            return ResolvedRef(
                ref=f"memx:evidence:local:{evidence_id}",
                status=ResolveStatus.RESOLVED,
                summary=data.get("summary", data.get("title", "")),
                metadata={"kind": data.get("kind"), "source": data.get("source")},
                raw_available=True,
            )
        except Exception as e:
            return ResolvedRef(
                ref=f"memx:evidence:local:{evidence_id}",
                status=ResolveStatus.UNRESOLVED,
                error_message=str(e),
            )

    def _resolve_knowledge(self, knowledge_id: str) -> ResolvedRef:
        """Resolve knowledge entity."""
        if not self._fetch_knowledge:
            return ResolvedRef(
                ref=f"memx:knowledge:local:{knowledge_id}",
                status=ResolveStatus.UNRESOLVED,
                error_message="No knowledge fetch callback configured",
            )

        try:
            data = self._fetch_knowledge(knowledge_id)
            if not data:
                return ResolvedRef(
                    ref=f"memx:knowledge:local:{knowledge_id}",
                    status=ResolveStatus.UNRESOLVED,
                    error_message=f"Knowledge not found: {knowledge_id}",
                )

            return ResolvedRef(
                ref=f"memx:knowledge:local:{knowledge_id}",
                status=ResolveStatus.RESOLVED,
                summary=data.get("summary", data.get("title", "")),
                metadata={"category": data.get("category")},
                raw_available=True,
            )
        except Exception as e:
            return ResolvedRef(
                ref=f"memx:knowledge:local:{knowledge_id}",
                status=ResolveStatus.UNRESOLVED,
                error_message=str(e),
            )

    def _resolve_chunk(self, chunk_id: str) -> ResolvedRef:
        """Resolve chunk entity."""
        if not self._fetch_chunk:
            return ResolvedRef(
                ref=f"memx:chunk:local:{chunk_id}",
                status=ResolveStatus.UNRESOLVED,
                error_message="No chunk fetch callback configured",
            )

        try:
            data = self._fetch_chunk(chunk_id)
            if not data:
                return ResolvedRef(
                    ref=f"memx:chunk:local:{chunk_id}",
                    status=ResolveStatus.UNRESOLVED,
                    error_message=f"Chunk not found: {chunk_id}",
                )

            return ResolvedRef(
                ref=f"memx:chunk:local:{chunk_id}",
                status=ResolveStatus.RESOLVED,
                summary=data.get("summary", ""),
                metadata={"doc_ref": data.get("doc_ref")},
                raw_available=True,
            )
        except Exception as e:
            return ResolvedRef(
                ref=f"memx:chunk:local:{chunk_id}",
                status=ResolveStatus.UNRESOLVED,
                error_message=str(e),
            )

    def load_summary(self, ref: str) -> Optional[SummaryPayload]:
        """Load summary for a memx entity."""
        result = self.resolve(ref)
        if result.status == ResolveStatus.RESOLVED and result.summary:
            return SummaryPayload(
                ref=ref,
                summary=result.summary,
                metadata=result.metadata or {},
            )
        return None

    def load_raw(self, ref: str, selector: Optional[Dict[str, Any]] = None) -> Optional[RawPayload]:
        """Load raw content for a memx entity."""
        from .typed_ref import parse_ref
        try:
            parsed = parse_ref(ref)
            entity_id = parsed.entity_id

            if parsed.entity_type == "evidence" and self._fetch_evidence:
                data = self._fetch_evidence(entity_id)
            elif parsed.entity_type == "knowledge" and self._fetch_knowledge:
                data = self._fetch_knowledge(entity_id)
            elif parsed.entity_type == "chunk" and self._fetch_chunk:
                data = self._fetch_chunk(entity_id)
            else:
                return None

            if not data:
                return None

            import json
            return RawPayload(
                ref=ref,
                content=json.dumps(data, ensure_ascii=False),
                metadata={"entity_type": parsed.entity_type},
            )
        except Exception:
            return None
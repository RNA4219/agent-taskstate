"""
Tracker Bridge Module

Provides minimum integration with external issue trackers.
Tracker is auxiliary - not the source of truth for internal state.

Features:
- Issue fetch and cache
- Entity linking (tracker:issue <-> agent-taskstate:task)
- Sync event tracking
- Snapshot export for context build
- Outbound status/comment reflection
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol

from .typed_ref import canonicalize_ref, format_ref, parse_ref


class SyncDirection(Enum):
    """Direction of sync."""

    INBOUND = "inbound"
    OUTBOUND = "outbound"


class SyncStatus(Enum):
    """Status of sync operation."""

    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"


class LinkRole(Enum):
    """Role of entity link."""

    PRIMARY = "primary"
    RELATED = "related"
    DUPLICATE = "duplicate"
    BLOCKS = "blocks"


@dataclass
class TrackerConnection:
    """Connection configuration for a tracker."""

    id: str
    provider: str
    name: str
    config_json: str
    created_at: str
    updated_at: str


@dataclass
class IssueCache:
    """Cached issue from external tracker."""

    id: str
    connection_id: str
    issue_ref: str
    remote_key: str
    title: str
    status: str
    assignee: Optional[str]
    description: Optional[str]
    labels_json: Optional[str]
    raw_json: Optional[str]
    fetched_at: str
    updated_at: str


@dataclass
class EntityLink:
    """Link between tracker issue and agent-taskstate entity."""

    id: str
    tracker_issue_ref: str
    agent_taskstate_entity_ref: str
    role: str
    created_at: str


@dataclass
class SyncEvent:
    """Record of sync operation."""

    id: str
    connection_id: str
    direction: str
    status: str
    issue_ref: Optional[str]
    details_json: Optional[str]
    error_message: Optional[str]
    created_at: str


@dataclass
class IssueSnapshot:
    """Minimal snapshot for context build."""

    issue_ref: str
    remote_key: str
    title: str
    status: str
    assignee: Optional[str]
    updated_at: str
    last_sync_result: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "issue_ref": self.issue_ref,
            "remote_key": self.remote_key,
            "title": self.title,
            "status": self.status,
            "assignee": self.assignee,
            "updated_at": self.updated_at,
            "last_sync_result": self.last_sync_result,
        }


@dataclass
class SyncSuggestion:
    """Suggestion for agent-taskstate update based on tracker change."""

    issue_ref: str
    agent_taskstate_task_ref: str
    suggested_action: str
    suggested_value: str
    reason: str
    requires_confirmation: bool = True


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def gen_id() -> str:
    import uuid

    return uuid.uuid4().hex


class TrackerAdapter(Protocol):
    """Protocol for tracker adapters."""

    def fetch_issue(self, issue_key: str) -> Optional[Dict[str, Any]]:
        ...

    def normalize_issue(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        ...

    def post_comment(self, issue_key: str, comment: str) -> bool:
        ...

    def update_status(self, issue_key: str, status: str) -> bool:
        ...


class MockTrackerAdapter:
    """Mock adapter for testing."""

    def __init__(self, issues: Optional[Dict[str, Dict[str, Any]]] = None):
        self.issues = issues or {}

    def fetch_issue(self, issue_key: str) -> Optional[Dict[str, Any]]:
        return self.issues.get(issue_key)

    def normalize_issue(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "remote_key": raw.get("key"),
            "title": raw.get("summary", ""),
            "status": raw.get("status", "unknown"),
            "assignee": raw.get("assignee"),
            "description": raw.get("description"),
        }

    def post_comment(self, issue_key: str, comment: str) -> bool:
        return True

    def update_status(self, issue_key: str, status: str) -> bool:
        return True


class TrackerBridgeService:
    """Service for tracker-bridge integration."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self._adapters: Dict[str, TrackerAdapter] = {}

    def register_adapter(self, provider: str, adapter: TrackerAdapter) -> None:
        """Register an adapter for a provider."""
        self._adapters[provider] = adapter

    def _normalize_issue_ref(self, issue_ref: str) -> str:
        """Canonicalize and validate a tracker issue reference."""
        try:
            canonical_ref = canonicalize_ref(issue_ref)
            parsed = parse_ref(canonical_ref)
        except ValueError as exc:
            raise ValueError("issue_ref must be a tracker issue typed_ref") from exc
        if parsed.domain != "tracker" or parsed.entity_type != "issue":
            raise ValueError("issue_ref must be a tracker issue typed_ref")
        return canonical_ref

    def _normalize_task_ref(self, task_ref: str) -> str:
        """Canonicalize and validate an agent-taskstate task reference."""
        try:
            canonical_ref = canonicalize_ref(task_ref)
            parsed = parse_ref(canonical_ref)
        except ValueError as exc:
            raise ValueError(
                "task_ref must be an agent-taskstate local task typed_ref"
            ) from exc
        if (
            parsed.domain != "agent-taskstate"
            or parsed.entity_type != "task"
            or parsed.provider != "local"
        ):
            raise ValueError(
                "task_ref must be an agent-taskstate local task typed_ref"
            )
        return canonical_ref

    def _normalize_link_role(self, role: str) -> str:
        """Validate and normalize link role values."""
        if isinstance(role, LinkRole):
            return role.value
        try:
            return LinkRole(role).value
        except ValueError as exc:
            raise ValueError(f"Invalid link role: {role}") from exc

    def create_connection(
        self,
        provider: str,
        name: str,
        config: Dict[str, Any],
    ) -> TrackerConnection:
        """Create a new tracker connection."""
        conn_id = gen_id()
        now = now_utc()

        self.conn.execute(
            """
            INSERT INTO tracker_connection
                (id, provider, name, config_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (conn_id, provider, name, json.dumps(config), now, now),
        )

        return TrackerConnection(
            id=conn_id,
            provider=provider,
            name=name,
            config_json=json.dumps(config),
            created_at=now,
            updated_at=now,
        )

    def fetch_issue(
        self,
        connection_id: str,
        issue_key: str,
    ) -> Optional[IssueCache]:
        """Fetch an issue from external tracker and cache it."""
        cursor = self.conn.execute(
            "SELECT id, provider FROM tracker_connection WHERE id = ?",
            (connection_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None

        provider = row["provider"]
        adapter = self._adapters.get(provider)
        if not adapter:
            self._record_sync_event(
                connection_id=connection_id,
                direction=SyncDirection.INBOUND,
                status=SyncStatus.FAILED,
                issue_ref=format_ref("tracker", "issue", issue_key, provider),
                details={"action": "fetch", "issue_key": issue_key},
                error_message=f"No adapter registered for provider: {provider}",
            )
            return None

        raw = adapter.fetch_issue(issue_key)
        if not raw:
            self._record_sync_event(
                connection_id=connection_id,
                direction=SyncDirection.INBOUND,
                status=SyncStatus.FAILED,
                issue_ref=format_ref("tracker", "issue", issue_key, provider),
                details={"action": "fetch", "issue_key": issue_key},
                error_message=f"Issue not found: {issue_key}",
            )
            return None

        normalized = adapter.normalize_issue(raw)
        remote_key = normalized["remote_key"]
        issue_ref = format_ref("tracker", "issue", remote_key, provider)
        cache_id = gen_id()
        now = now_utc()

        self.conn.execute(
            """
            INSERT OR REPLACE INTO issue_cache
                (id, connection_id, issue_ref, remote_key, title, status,
                 assignee, description, labels_json, raw_json, fetched_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                cache_id,
                connection_id,
                issue_ref,
                remote_key,
                normalized["title"],
                normalized["status"],
                normalized.get("assignee"),
                normalized.get("description"),
                json.dumps(normalized.get("labels", [])),
                json.dumps(raw),
                now,
                now,
            ),
        )

        self._record_sync_event(
            connection_id=connection_id,
            direction=SyncDirection.INBOUND,
            status=SyncStatus.SUCCESS,
            issue_ref=issue_ref,
            details={"action": "fetch", "issue_key": issue_key},
        )

        return IssueCache(
            id=cache_id,
            connection_id=connection_id,
            issue_ref=issue_ref,
            remote_key=remote_key,
            title=normalized["title"],
            status=normalized["status"],
            assignee=normalized.get("assignee"),
            description=normalized.get("description"),
            labels_json=json.dumps(normalized.get("labels", [])),
            raw_json=json.dumps(raw),
            fetched_at=now,
            updated_at=now,
        )

    def link_issue_to_task(
        self,
        issue_ref: str,
        task_ref: str,
        role: str = "primary",
    ) -> EntityLink:
        """Link a tracker issue to an agent-taskstate task."""
        issue_ref = self._normalize_issue_ref(issue_ref)
        task_ref = self._normalize_task_ref(task_ref)
        role = self._normalize_link_role(role)
        link_id = gen_id()
        now = now_utc()

        self.conn.execute(
            """
            INSERT INTO entity_link
                (id, tracker_issue_ref, agent_taskstate_entity_ref, role, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (link_id, issue_ref, task_ref, role, now),
        )

        return EntityLink(
            id=link_id,
            tracker_issue_ref=issue_ref,
            agent_taskstate_entity_ref=task_ref,
            role=role,
            created_at=now,
        )

    def get_issue_links(self, issue_ref: str) -> List[EntityLink]:
        """Get all links for an issue."""
        issue_ref = self._normalize_issue_ref(issue_ref)
        cursor = self.conn.execute(
            """
            SELECT id, tracker_issue_ref, agent_taskstate_entity_ref, role, created_at
            FROM entity_link
            WHERE tracker_issue_ref = ?
            """,
            (issue_ref,),
        )

        links = []
        for row in cursor.fetchall():
            links.append(
                EntityLink(
                    id=row[0],
                    tracker_issue_ref=row[1],
                    agent_taskstate_entity_ref=row[2],
                    role=row[3],
                    created_at=row[4],
                )
            )
        return links

    def get_task_links(self, task_ref: str) -> List[EntityLink]:
        """Get all tracker links for a task."""
        task_ref = self._normalize_task_ref(task_ref)
        cursor = self.conn.execute(
            """
            SELECT id, tracker_issue_ref, agent_taskstate_entity_ref, role, created_at
            FROM entity_link
            WHERE agent_taskstate_entity_ref = ?
            """,
            (task_ref,),
        )

        links = []
        for row in cursor.fetchall():
            links.append(
                EntityLink(
                    id=row[0],
                    tracker_issue_ref=row[1],
                    agent_taskstate_entity_ref=row[2],
                    role=row[3],
                    created_at=row[4],
                )
            )
        return links

    def get_issue_snapshot(self, issue_ref: str) -> Optional[IssueSnapshot]:
        """Get minimal snapshot for context build."""
        issue_ref = self._normalize_issue_ref(issue_ref)
        cursor = self.conn.execute(
            """
            SELECT issue_ref, remote_key, title, status, assignee, updated_at
            FROM issue_cache
            WHERE issue_ref = ?
            """,
            (issue_ref,),
        )

        row = cursor.fetchone()
        if not row:
            return None

        sync_cursor = self.conn.execute(
            """
            SELECT status
            FROM sync_event
            WHERE issue_ref = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (issue_ref,),
        )
        sync_row = sync_cursor.fetchone()

        return IssueSnapshot(
            issue_ref=row[0],
            remote_key=row[1],
            title=row[2],
            status=row[3],
            assignee=row[4],
            updated_at=row[5],
            last_sync_result=sync_row[0] if sync_row else "unknown",
        )

    def post_outbound_comment(
        self,
        connection_id: str,
        issue_key: str,
        comment: str,
    ) -> bool:
        """Post a comment to external tracker (outbound)."""
        cursor = self.conn.execute(
            "SELECT provider FROM tracker_connection WHERE id = ?",
            (connection_id,),
        )
        row = cursor.fetchone()
        if not row:
            return False

        provider = row["provider"]
        adapter = self._adapters.get(provider)
        if not adapter:
            self._record_sync_event(
                connection_id=connection_id,
                direction=SyncDirection.OUTBOUND,
                status=SyncStatus.FAILED,
                issue_ref=format_ref("tracker", "issue", issue_key, provider),
                details={"action": "post_comment"},
                error_message=f"No adapter registered for provider: {provider}",
            )
            return False

        success = adapter.post_comment(issue_key, comment)
        issue_ref = format_ref("tracker", "issue", issue_key, provider)

        self._record_sync_event(
            connection_id=connection_id,
            direction=SyncDirection.OUTBOUND,
            status=SyncStatus.SUCCESS if success else SyncStatus.FAILED,
            issue_ref=issue_ref,
            details={"action": "post_comment"},
            error_message=None if success else f"Failed to post comment: {issue_key}",
        )

        return success

    def update_outbound_status(
        self,
        connection_id: str,
        issue_key: str,
        status: str,
    ) -> bool:
        """Reflect an internal status to the external tracker."""
        cursor = self.conn.execute(
            "SELECT provider FROM tracker_connection WHERE id = ?",
            (connection_id,),
        )
        row = cursor.fetchone()
        if not row:
            return False

        provider = row["provider"]
        adapter = self._adapters.get(provider)
        issue_ref = format_ref("tracker", "issue", issue_key, provider)
        if not adapter:
            self._record_sync_event(
                connection_id=connection_id,
                direction=SyncDirection.OUTBOUND,
                status=SyncStatus.FAILED,
                issue_ref=issue_ref,
                details={"action": "update_status", "status": status},
                error_message=f"No adapter registered for provider: {provider}",
            )
            return False

        success = adapter.update_status(issue_key, status)

        self._record_sync_event(
            connection_id=connection_id,
            direction=SyncDirection.OUTBOUND,
            status=SyncStatus.SUCCESS if success else SyncStatus.FAILED,
            issue_ref=issue_ref,
            details={"action": "update_status", "status": status},
            error_message=None if success else f"Failed to update status: {issue_key}",
        )

        return success

    def generate_sync_suggestions(
        self,
        issue_ref: str,
    ) -> List[SyncSuggestion]:
        """Generate suggestions for agent-taskstate updates based on tracker changes."""
        suggestions = []
        snapshot = self.get_issue_snapshot(issue_ref)
        if not snapshot:
            return suggestions

        links = self.get_issue_links(issue_ref)
        for link in links:
            if link.role == "primary":
                suggestions.append(
                    SyncSuggestion(
                        issue_ref=issue_ref,
                        agent_taskstate_task_ref=link.agent_taskstate_entity_ref,
                        suggested_action="review_status",
                        suggested_value=snapshot.status,
                        reason=f"Tracker status is '{snapshot.status}'",
                        requires_confirmation=True,
                    )
                )

        return suggestions

    def get_sync_events(
        self,
        connection_id: Optional[str] = None,
        issue_ref: Optional[str] = None,
        limit: int = 100,
    ) -> List[SyncEvent]:
        """Get sync events for tracking."""
        query = """
            SELECT id, connection_id, direction, status, issue_ref,
                   details_json, error_message, created_at
            FROM sync_event
            WHERE 1=1
        """
        params = []

        if connection_id:
            query += " AND connection_id = ?"
            params.append(connection_id)
        if issue_ref:
            issue_ref = self._normalize_issue_ref(issue_ref)
            query += " AND issue_ref = ?"
            params.append(issue_ref)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        cursor = self.conn.execute(query, params)

        events = []
        for row in cursor.fetchall():
            events.append(
                SyncEvent(
                    id=row[0],
                    connection_id=row[1],
                    direction=row[2],
                    status=row[3],
                    issue_ref=row[4],
                    details_json=row[5],
                    error_message=row[6],
                    created_at=row[7],
                )
            )
        return events

    def _record_sync_event(
        self,
        connection_id: str,
        direction: SyncDirection,
        status: SyncStatus,
        issue_ref: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
    ) -> SyncEvent:
        """Record a sync event."""
        event_id = gen_id()
        now = now_utc()

        self.conn.execute(
            """
            INSERT INTO sync_event
                (id, connection_id, direction, status, issue_ref,
                 details_json, error_message, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                connection_id,
                direction.value,
                status.value,
                issue_ref,
                json.dumps(details) if details else None,
                error_message,
                now,
            ),
        )

        return SyncEvent(
            id=event_id,
            connection_id=connection_id,
            direction=direction.value,
            status=status.value,
            issue_ref=issue_ref,
            details_json=json.dumps(details) if details else None,
            error_message=error_message,
            created_at=now,
        )


def create_tracker_tables(conn: sqlite3.Connection) -> None:
    """Create tracker-bridge tables."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tracker_connection (
            id TEXT PRIMARY KEY,
            provider TEXT NOT NULL,
            name TEXT NOT NULL,
            config_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS issue_cache (
            id TEXT PRIMARY KEY,
            connection_id TEXT NOT NULL,
            issue_ref TEXT NOT NULL UNIQUE,
            remote_key TEXT NOT NULL,
            title TEXT NOT NULL,
            status TEXT NOT NULL,
            assignee TEXT,
            description TEXT,
            labels_json TEXT,
            raw_json TEXT,
            fetched_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (connection_id) REFERENCES tracker_connection(id)
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS entity_link (
            id TEXT PRIMARY KEY,
            tracker_issue_ref TEXT NOT NULL,
            agent_taskstate_entity_ref TEXT NOT NULL,
            role TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sync_event (
            id TEXT PRIMARY KEY,
            connection_id TEXT NOT NULL,
            direction TEXT NOT NULL,
            status TEXT NOT NULL,
            issue_ref TEXT,
            details_json TEXT,
            error_message TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (connection_id) REFERENCES tracker_connection(id)
        )
        """
    )

    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_issue_cache_ref
        ON issue_cache(issue_ref)
        """
    )

    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_entity_link_issue
        ON entity_link(tracker_issue_ref)
        """
    )

    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_entity_link_task
        ON entity_link(agent_taskstate_entity_ref)
        """
    )

    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_sync_event_connection
        ON sync_event(connection_id, created_at DESC)
        """
    )


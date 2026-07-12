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
    secret_env_json: str
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

    def fetch_issue(self, issue_key: str) -> Optional[Dict[str, Any]]: ...

    def normalize_issue(self, raw: Dict[str, Any]) -> Dict[str, Any]: ...

    def post_comment(self, issue_key: str, comment: str) -> bool: ...

    def update_status(self, issue_key: str, status: str) -> bool: ...


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


class GitHubAdapter:
    """
    GitHub Issues adapter using PyGithub.

    Requires: PyGithub package (pip install PyGithub)

    Config:
    - token: GitHub personal access token
    - repo_owner: Repository owner
    - repo_name: Repository name
    """

    def __init__(self, token: str, repo_owner: str, repo_name: str):
        self._token = token
        self._repo_owner = repo_owner
        self._repo_name = repo_name
        self._repo = None

    def _get_repo(self):
        """Lazy-load repository."""
        if self._repo is None:
            try:
                from github import Github

                gh = Github(self._token)
                self._repo = gh.get_repo(f"{self._repo_owner}/{self._repo_name}")
            except ImportError:
                raise RuntimeError("PyGithub not installed. Run: pip install PyGithub")
        return self._repo

    def parse_issue_key(self, issue_key: str) -> int:
        """Parse issue number from key (e.g., 'owner/repo#123' or '#123')."""
        if "#" in issue_key:
            return int(issue_key.split("#")[-1])
        return int(issue_key)

    def fetch_issue(self, issue_key: str) -> Optional[Dict[str, Any]]:
        """Fetch issue from GitHub."""
        try:
            repo = self._get_repo()
            issue_num = self.parse_issue_key(issue_key)
            issue = repo.get_issue(issue_num)
            return {
                "key": f"{self._repo_owner}/{self._repo_name}#{issue_num}",
                "number": issue_num,
                "title": issue.title,
                "body": issue.body or "",
                "state": issue.state,
                "assignee": issue.assignee.login if issue.assignee else None,
                "labels": [label.name for label in issue.labels],
                "created_at": issue.created_at.isoformat(),
                "updated_at": issue.updated_at.isoformat(),
                "url": issue.html_url,
            }
        except Exception:
            return None

    def normalize_issue(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize GitHub issue to standard format."""
        labels = raw.get("labels", [])
        if isinstance(labels, str):
            labels = [labels]
        return {
            "remote_key": raw.get("key"),
            "title": raw.get("title", ""),
            "status": raw.get("state", "open"),
            "assignee": raw.get("assignee"),
            "description": raw.get("body"),
            "labels": labels,
            "url": raw.get("url"),
        }

    def post_comment(self, issue_key: str, comment: str) -> bool:
        """Post comment to GitHub issue."""
        try:
            repo = self._get_repo()
            issue_num = self.parse_issue_key(issue_key)
            issue = repo.get_issue(issue_num)
            issue.create_comment(comment)
            return True
        except Exception:
            return False

    def update_status(self, issue_key: str, status: str) -> bool:
        """Update GitHub issue status (open/closed)."""
        try:
            repo = self._get_repo()
            issue_num = self.parse_issue_key(issue_key)
            issue = repo.get_issue(issue_num)
            if status.lower() == "closed":
                issue.edit(state="closed")
            elif status.lower() == "open":
                issue.edit(state="open")
            return True
        except Exception:
            return False


class JiraAdapter:
    """
    Jira adapter using jira library.

    Requires: jira package (pip install jira)

    Config:
    - server: Jira server URL
    - username: Jira username/email
    - password: Jira password or API token
    """

    def __init__(self, server: str, username: str, password: str):
        self._server = server
        self._username = username
        self._password = password
        self._jira = None

    def _get_jira(self):
        """Lazy-load Jira client."""
        if self._jira is None:
            try:
                from jira import JIRA

                self._jira = JIRA(
                    server=self._server,
                    basic_auth=(self._username, self._password),
                )
            except ImportError:
                raise RuntimeError("jira not installed. Run: pip install jira")
        return self._jira

    def fetch_issue(self, issue_key: str) -> Optional[Dict[str, Any]]:
        """Fetch issue from Jira."""
        try:
            jira = self._get_jira()
            issue = jira.issue(issue_key)
            return {
                "key": issue.key,
                "summary": issue.fields.summary,
                "description": issue.fields.description or "",
                "status": issue.fields.status.name,
                "assignee": issue.fields.assignee.displayName if issue.fields.assignee else None,
                "priority": issue.fields.priority.name if issue.fields.priority else None,
                "labels": [label.name for label in issue.fields.labels],
                "created_at": issue.fields.created.isoformat() if issue.fields.created else None,
                "updated_at": issue.fields.updated.isoformat() if issue.fields.updated else None,
                "url": f"{self._server}/browse/{issue.key}",
            }
        except Exception:
            return None

    def normalize_issue(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize Jira issue to standard format."""
        labels = raw.get("labels", [])
        if isinstance(labels, str):
            labels = [labels]
        return {
            "remote_key": raw.get("key"),
            "title": raw.get("summary", ""),
            "status": raw.get("status", "unknown"),
            "assignee": raw.get("assignee"),
            "description": raw.get("description"),
            "priority": raw.get("priority"),
            "labels": labels,
            "url": raw.get("url"),
        }

    def post_comment(self, issue_key: str, comment: str) -> bool:
        """Post comment to Jira issue."""
        try:
            jira = self._get_jira()
            issue = jira.issue(issue_key)
            jira.add_comment(issue, comment)
            return True
        except Exception:
            return False

    def update_status(self, issue_key: str, status: str) -> bool:
        """Update Jira issue status (transition)."""
        try:
            jira = self._get_jira()
            issue = jira.issue(issue_key)
            transitions = jira.transitions(issue)
            for t in transitions:
                if t["name"].lower() == status.lower():
                    jira.transition_issue(issue, t["id"])
                    return True
            return False
        except Exception:
            return False


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
            raise ValueError("task_ref must be an agent-taskstate local task typed_ref") from exc
        if (
            parsed.domain != "agent-taskstate"
            or parsed.entity_type != "task"
            or parsed.provider != "local"
        ):
            raise ValueError("task_ref must be an agent-taskstate local task typed_ref")
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
        secret_env: Optional[Dict[str, str]] = None,
    ) -> TrackerConnection:
        """Create a connection without persisting secret values."""
        if _contains_secret_key(config):
            raise ValueError("secret values must not be stored; use secret_env")
        secret_env = secret_env or {}
        if any(
            not isinstance(key, str) or not isinstance(value, str)
            for key, value in secret_env.items()
        ):
            raise ValueError("secret_env must map names to environment variable names")
        conn_id = gen_id()
        now = now_utc()
        config_json = json.dumps(_redact(config), ensure_ascii=False)
        secret_env_json = json.dumps(secret_env, ensure_ascii=False)
        self.conn.execute(
            """
            INSERT INTO tracker_connection
                (id, provider, name, config_json, secret_env_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (conn_id, provider, name, config_json, secret_env_json, now, now),
        )
        return TrackerConnection(
            id=conn_id,
            provider=provider,
            name=name,
            config_json=config_json,
            secret_env_json=secret_env_json,
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

        try:
            raw = adapter.fetch_issue(issue_key)
        except Exception as exc:
            self._record_sync_event(
                connection_id=connection_id,
                direction=SyncDirection.INBOUND,
                status=SyncStatus.FAILED,
                issue_ref=format_ref("tracker", "issue", issue_key, provider),
                details={"action": "fetch", "error_class": classify_adapter_exception(exc)},
                error_message=f"adapter error ({classify_adapter_exception(exc)})",
            )
            return None
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
        suggestions: List[SyncSuggestion] = []
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
        params: List[Any] = []

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
                json.dumps(_redact(details), ensure_ascii=False) if details else None,
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
            details_json=json.dumps(_redact(details), ensure_ascii=False) if details else None,
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
            secret_env_json TEXT NOT NULL DEFAULT '{}',
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


_SECRET_KEYS = {"token", "password", "secret", "api_key", "apikey", "client_secret"}


def _contains_secret_key(value: Any) -> bool:
    if isinstance(value, dict):
        return any(
            key.lower() in _SECRET_KEYS or _contains_secret_key(item) for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_contains_secret_key(item) for item in value)
    return False


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: ("[REDACTED]" if key.lower() in _SECRET_KEYS else _redact(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def classify_adapter_exception(exc: Exception) -> str:
    name, message = type(exc).__name__.lower(), str(exc).lower()
    if "auth" in name or "unauthor" in message or "forbidden" in message or "credential" in message:
        return "auth"
    if "notfound" in name or "not found" in message:
        return "not-found"
    if "rate" in name or "rate limit" in message or "429" in message:
        return "rate-limit"
    if isinstance(exc, (ValueError, TypeError)) or "invalid" in message:
        return "validation"
    return "transport"

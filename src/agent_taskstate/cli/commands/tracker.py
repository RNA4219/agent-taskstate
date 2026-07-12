"""Explicit tracker CLI operations."""

from __future__ import annotations

import argparse
import json

from ...tracker_bridge import TrackerBridgeService
from .. import AppContext
from ..db import connect, init_db
from ..utils import json_ok
from ..validation import load_json_arg


def _bridge(ctx: AppContext):
    conn = connect(ctx.db_path)
    return conn


def cmd_tracker_connection_add(ctx: AppContext, args: argparse.Namespace) -> int:
    config = load_json_arg(args.json, args.file) if args.json or args.file else {}
    secret_env = json.loads(args.secret_env_json) if getattr(args, "secret_env_json", None) else {}
    with connect(ctx.db_path) as conn:
        init_db(conn)
        service = TrackerBridgeService(conn)
        connection = service.create_connection(
            args.provider, args.name, config, secret_env=secret_env
        )
    return json_ok(
        {
            "id": connection.id,
            "provider": connection.provider,
            "name": connection.name,
            "config": json.loads(connection.config_json),
            "secret_env": json.loads(connection.secret_env_json),
            "created_at": connection.created_at,
            "updated_at": connection.updated_at,
        }
    )


def cmd_tracker_fetch(ctx: AppContext, args: argparse.Namespace) -> int:
    with connect(ctx.db_path) as conn:
        init_db(conn)
        issue = TrackerBridgeService(conn).fetch_issue(args.connection, args.issue_key)
        if issue is None:
            return json_ok(
                {
                    "issue": None,
                    "diagnostics": {"unsupported": ["tracker adapter is not configured"]},
                }
            )
    return json_ok(
        {
            "id": issue.id,
            "connection_id": issue.connection_id,
            "issue_ref": issue.issue_ref,
            "remote_key": issue.remote_key,
            "title": issue.title,
            "status": issue.status,
            "assignee": issue.assignee,
            "description": issue.description,
            "labels": json.loads(issue.labels_json or "[]"),
            "fetched_at": issue.fetched_at,
            "updated_at": issue.updated_at,
        }
    )


def cmd_tracker_link(ctx: AppContext, args: argparse.Namespace) -> int:
    with connect(ctx.db_path) as conn:
        init_db(conn)
        link = TrackerBridgeService(conn).link_issue_to_task(args.issue_ref, args.task, args.role)
    return json_ok(vars(link))


def cmd_tracker_snapshot(ctx: AppContext, args: argparse.Namespace) -> int:
    with connect(ctx.db_path) as conn:
        init_db(conn)
        snapshot = TrackerBridgeService(conn).get_issue_snapshot(args.issue_ref)
    return json_ok(
        snapshot.to_dict()
        if snapshot
        else {"snapshot": None, "diagnostics": {"missing": [args.issue_ref]}}
    )


def cmd_tracker_events(ctx: AppContext, args: argparse.Namespace) -> int:
    with connect(ctx.db_path) as conn:
        init_db(conn)
        events = TrackerBridgeService(conn).get_sync_events(
            args.connection, args.issue_ref, args.limit
        )
    return json_ok([vars(event) for event in events])


def cmd_tracker_suggest(ctx: AppContext, args: argparse.Namespace) -> int:
    with connect(ctx.db_path) as conn:
        init_db(conn)
        suggestions = TrackerBridgeService(conn).generate_sync_suggestions(args.issue_ref)
    return json_ok([vars(item) for item in suggestions])


def cmd_tracker_comment(ctx: AppContext, args: argparse.Namespace) -> int:
    with connect(ctx.db_path) as conn:
        init_db(conn)
        ok = TrackerBridgeService(conn).post_outbound_comment(
            args.connection, args.issue_key, args.comment
        )
    return json_ok({"ok": ok, "outbound": True})


def cmd_tracker_status(ctx: AppContext, args: argparse.Namespace) -> int:
    with connect(ctx.db_path) as conn:
        init_db(conn)
        ok = TrackerBridgeService(conn).update_outbound_status(
            args.connection, args.issue_key, args.status
        )
    return json_ok({"ok": ok, "outbound": True})

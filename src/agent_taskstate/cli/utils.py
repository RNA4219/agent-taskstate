"""
CLI Utility Functions
"""

from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime, timezone
from typing import Any

from .constants import ISO


def now_utc() -> str:
    """Return current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).strftime(ISO)


def gen_id() -> str:
    """Generate unique ID."""
    return uuid.uuid4().hex


def json_ok(data: Any) -> int:
    """Output success JSON and return 0."""
    print(json.dumps({"ok": True, "data": data, "error": None}, ensure_ascii=False, indent=2))
    return 0


def json_error(code: str, message: str) -> int:
    """Output error JSON and return 1."""
    print(
        json.dumps(
            {"ok": False, "data": None, "error": {"code": code, "message": message}},
            ensure_ascii=False,
            indent=2,
        ),
        file=sys.stdout,
    )
    return 1

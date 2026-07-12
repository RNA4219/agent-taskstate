"""Canonical CLI entry point."""

from __future__ import annotations

import json
import sqlite3
import sys
import traceback
from dataclasses import dataclass


@dataclass
class AppContext:
    db_path: str


def main(argv: list[str] | None = None) -> int:
    from .errors import AgentTaskstateError
    from .parser import build_parser
    from .utils import json_error

    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 2
    ctx = AppContext(db_path=args.db)
    try:
        return int(args.func(ctx, args))
    except AgentTaskstateError as exc:
        return json_error(exc.code, str(exc))
    except (sqlite3.IntegrityError, json.JSONDecodeError) as exc:
        return json_error("validation_error", str(exc))
    except Exception:
        traceback.print_exc(file=sys.stderr)
        return json_error("internal_error", "unexpected internal error; see stderr for details")


if __name__ == "__main__":
    raise SystemExit(main())

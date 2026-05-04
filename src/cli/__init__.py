"""
CLI Package

agent-taskstate command-line interface.
"""

from __future__ import annotations

from dataclasses import dataclass

from .constants import APP_NAME, DEFAULT_DB_PATH


@dataclass
class AppContext:
    """CLI application context."""
    db_path: str


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    import json
    import sqlite3

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
    except AgentTaskstateError as e:
        return json_error(e.code, str(e))
    except sqlite3.IntegrityError as e:
        return json_error("validation_error", f"sqlite integrity error: {e}")
    except json.JSONDecodeError as e:
        return json_error("validation_error", f"invalid JSON: {e}")
    except Exception as e:
        return json_error("validation_error", f"unexpected error: {e}")


if __name__ == "__main__":
    raise SystemExit(main())
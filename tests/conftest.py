"""
workx Test Configuration

pytest fixtures for testing workx CLI.
"""

from pathlib import Path
from typing import Generator

import pytest

# Import helpers which loads the workx module
from .helpers import workx, create_task, create_task_state, create_decision, create_open_question, create_run, create_context_bundle


@pytest.fixture
def tmp_db_path(tmp_path: Path) -> str:
    """Create a temporary database path for testing."""
    return str(tmp_path / "test_workx.db")


@pytest.fixture
def empty_db(tmp_db_path: str) -> str:
    """Create an empty database and return its path."""
    # Initialize the database schema
    with workx.connect(tmp_db_path) as conn:
        conn.executescript(workx.SCHEMA_SQL)
    return tmp_db_path


@pytest.fixture
def app_context(empty_db: str) -> workx.AppContext:
    """Create an application context with test database."""
    return workx.AppContext(db_path=empty_db)


# Re-export helpers for convenience
__all__ = [
    "tmp_db_path",
    "empty_db",
    "app_context",
    "workx",
    "create_task",
    "create_task_state",
    "create_decision",
    "create_open_question",
    "create_run",
    "create_context_bundle",
]
"""
agent-taskstate Test Configuration

pytest fixtures for testing agent-taskstate CLI.
"""

from pathlib import Path

import pytest

# Import helpers which loads the agent_taskstate module
from .helpers import agent_taskstate, create_task, create_task_state, create_decision, create_open_question, create_run, create_context_bundle


@pytest.fixture
def tmp_db_path(tmp_path: Path) -> str:
    """Create a temporary database path for testing."""
    return str(tmp_path / "test_agent_taskstate.db")


@pytest.fixture
def empty_db(tmp_db_path: str) -> str:
    """Create an empty database and return its path."""
    # Initialize the database schema
    with agent_taskstate.connect(tmp_db_path) as conn:
        conn.executescript(agent_taskstate.SCHEMA_SQL)
    return tmp_db_path


@pytest.fixture
def app_context(empty_db: str) -> agent_taskstate.AppContext:
    """Create an application context with test database."""
    return agent_taskstate.AppContext(db_path=empty_db)


# Re-export helpers for convenience
__all__ = [
    "tmp_db_path",
    "empty_db",
    "app_context",
    "agent_taskstate",
    "create_task",
    "create_task_state",
    "create_decision",
    "create_open_question",
    "create_run",
    "create_context_bundle",
]
"""Deprecated compatibility shim for agent_taskstate.cli."""

from __future__ import annotations

import warnings

warnings.warn(
    "src.cli is deprecated; import agent_taskstate.cli instead.",
    DeprecationWarning,
    stacklevel=2,
)

from agent_taskstate.cli import AppContext, main
from agent_taskstate.cli.constants import *
from agent_taskstate.cli.db import *
from agent_taskstate.cli.errors import *
from agent_taskstate.cli.fetch import *
from agent_taskstate.cli.models import *
from agent_taskstate.cli.utils import *
from agent_taskstate.cli.validation import *
from agent_taskstate.cli.commands import *

"""Hierarchical multi-agent engine on the Claude Messages API.

The engine knows no concrete agents. Pass a roster of `AgentSpec`s and the root
key to `run_team`; `app.hierarchy` builds the roster from `backend/catalog`.
"""

from .agents import AgentSpec
from .api import new_run_id, run_team
from .config import Limits
from .events import ConsoleSink, Event, EventBus, JsonlSink
from .runtime import Orchestration, RunResult
from .workspace import Workspace

__all__ = [
    "AgentSpec",
    "ConsoleSink",
    "Event",
    "EventBus",
    "JsonlSink",
    "Limits",
    "Orchestration",
    "RunResult",
    "Workspace",
    "new_run_id",
    "run_team",
]

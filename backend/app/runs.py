"""Team runs. Each run gets a canvas, and an orchestrator fills it through the canvas tools.

Orchestrators: ``app.hierarchy`` runs the team on the Claude Messages API (the
coordinator delegates to members, members to helpers); ``app.dummy`` fills a
canvas without calling a model.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .catalog import Catalog, TeamSpec

# (tool_name, tool_input) -> tool_result, bound to one canvas.
CanvasTool = Callable[[str, dict[str, Any]], dict[str, Any]]


@dataclass
class RunContext:
    catalog: Catalog
    team: TeamSpec
    input_text: str
    canvas_id: int
    # The orchestrator's only channel to the UI. Call it as an agent calls a tool:
    # call_tool("add_block", {"version": 3, "block": {...}}).
    call_tool: CanvasTool


def add(ctx: RunContext, block: dict) -> str:
    version = ctx.call_tool("get_canvas", {})["version"]
    return ctx.call_tool("add_block", {"version": version, "block": block})["block_id"]


def update(ctx: RunContext, block_id: str, block: dict) -> None:
    version = ctx.call_tool("get_canvas", {})["version"]
    ctx.call_tool("update_block", {"version": version, "block_id": block_id, "block": block})

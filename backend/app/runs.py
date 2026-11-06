"""Team runs. Each run gets a canvas, and an orchestrator fills it through the canvas tools.

Orchestrators: ``app.hierarchy`` runs the team on the Claude Messages API (the
coordinator delegates to members, members to helpers); ``app.dummy`` fills a
canvas without calling a model.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from .catalog import Catalog, TeamSpec
from .rfps import Rfp

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
    # An uploaded PDF, when the input came as one. input_text then holds its text.
    rfp: Rfp | None = None
    # The org tree of the run: node id -> node, in insertion order; one org block.
    nodes: dict[str, dict] = field(default_factory=dict)
    org_id: str | None = None


def add(ctx: RunContext, block: dict) -> str:
    version = ctx.call_tool("get_canvas", {})["version"]
    return ctx.call_tool("add_block", {"version": version, "block": block})["block_id"]


def update(ctx: RunContext, block_id: str, block: dict) -> None:
    version = ctx.call_tool("get_canvas", {})["version"]
    ctx.call_tool("update_block", {"version": version, "block_id": block_id, "block": block})


def set_node(ctx: RunContext, node_id: str, **fields: Any) -> None:
    """Add or change one node of the org tree and rewrite the org block."""
    node = ctx.nodes.setdefault(node_id, {"id": node_id, "name": node_id, "agent": None, "parent": None})
    node.update(fields)
    block = {
        "type": "org",
        "title": "Team",
        "agent": ctx.team.coordinator,
        "props": {"nodes": list(ctx.nodes.values())},
    }
    if ctx.org_id:
        update(ctx, ctx.org_id, block)
    else:
        ctx.org_id = add(ctx, block)

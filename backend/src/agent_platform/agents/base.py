"""The contract between the platform and an agent runtime."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from ..catalog import Catalog, TeamSpec

# (tool_name, tool_input) -> tool_result. Bound to one canvas.
CanvasTool = Callable[[str, dict[str, Any]], dict[str, Any]]


@dataclass
class RunContext:
    catalog: Catalog
    team: TeamSpec
    input_text: str
    canvas_id: str
    # The orchestrator's only channel to the UI. Call it exactly as an agent
    # would call a tool: call_tool("add_block", {"version": 3, "block": {...}}).
    call_tool: CanvasTool


class Orchestrator(Protocol):
    """Runs one team against one input, reporting progress via canvas tools.

    ``run`` is called in a background thread and may block for as long as the
    run takes. Raise to fail the run; the platform marks it failed on the canvas.
    """

    def run(self, ctx: RunContext) -> None: ...

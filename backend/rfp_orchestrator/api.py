"""High-level entry point: one call = one team run."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict
from pathlib import Path

from .agents import AgentSpec
from .config import Limits
from .events import EventBus, EventSink, JsonlSink
from .runtime import Orchestration, RunResult
from .workspace import Workspace


def new_run_id() -> str:
    return uuid.uuid4().hex[:8]


async def run_team(
    *,
    roster: dict[str, AgentSpec],
    root_key: str,
    task: str,
    inputs: dict[str, str],
    workspace_root: Path,
    limits: Limits | None = None,
    sinks: list[EventSink] | None = None,
    run_id: str | None = None,
    client=None,
) -> RunResult:
    """Run `root_key` on `task`. `inputs` (file name -> text) land in inputs/."""
    ws = Workspace(workspace_root)
    for name, text in inputs.items():
        ws.write_input(name, text)

    bus = EventBus([JsonlSink(ws.root / "events.jsonl"), *(sinks or [])])
    orch = Orchestration(
        ws,
        roster,
        root_key,
        client=client,
        limits=limits or Limits.from_env(),
        bus=bus,
        run_id=run_id or new_run_id(),
    )
    result = await orch.run(task)
    (ws.root / "run-summary.json").write_text(json.dumps(asdict(result), indent=2, ensure_ascii=False))
    return result

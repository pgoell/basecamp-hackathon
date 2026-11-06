"""Team runs. Each run gets a canvas, and an orchestrator fills it through the canvas tools.

`managed` runs the team on Claude Managed Agents: it opens the session's event
stream, sends the kickoff, and turns events into canvas blocks (a status per
agent, the coordinator's messages, the files it wrote). The agents themselves
do not touch the canvas yet. `app.dummy` fills a canvas without calling a model.
"""

import asyncio
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import quote

from anthropic import AsyncAnthropic

from .catalog import Catalog, TeamSpec

SWARM_FILE = Path(__file__).resolve().parents[1] / "swarm.json"
BETAS = ["managed-agents-2026-04-01"]
# Files show up in the Files API a few seconds after the session ends.
FILES_DELAY = 3

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
    # Status block id per agent name, filled as the run goes.
    status: dict[str, str] = field(default_factory=dict)


def swarm() -> dict:
    return json.loads(SWARM_FILE.read_text()) if SWARM_FILE.exists() else {}


def kickoff(ctx: RunContext) -> str:
    docs = [f"=====  DOCUMENT: {ctx.team.input.label}  =====\n{ctx.input_text}"] + [
        f"=====  DOCUMENT: {name}  =====\n{ctx.catalog.read_knowledge(name)}" for name in ctx.team.context
    ]
    return ctx.team.kickoff.strip() + "\n\n" + "\n\n".join(docs)


def add(ctx: RunContext, block: dict) -> str:
    version = ctx.call_tool("get_canvas", {})["version"]
    return ctx.call_tool("add_block", {"version": version, "block": block})["block_id"]


def update(ctx: RunContext, block_id: str, block: dict) -> None:
    version = ctx.call_tool("get_canvas", {})["version"]
    ctx.call_tool("update_block", {"version": version, "block_id": block_id, "block": block})


def set_status(ctx: RunContext, name: str, state: str, detail: str | None = None) -> None:
    key = next((a.key for a in ctx.catalog.agents.values() if a.name == name), None)
    block = {"type": "status", "title": name, "agent": key, "props": {"state": state}}
    if detail:
        block["props"]["detail"] = detail
    if name in ctx.status:
        update(ctx, ctx.status[name], block)
    else:
        ctx.status[name] = add(ctx, block)


async def managed(ctx: RunContext) -> None:
    ids = swarm()
    coordinator_id = ids.get("agents", {}).get(ctx.team.coordinator)
    if not coordinator_id:
        raise RuntimeError(f"No agent id for '{ctx.team.coordinator}' in swarm.json. Run the setup-agents workflow.")
    client = AsyncAnthropic()
    session = await client.beta.sessions.create(
        agent=coordinator_id, environment_id=ids["environment_id"], title=f"{ctx.team.name} run"
    )
    console = f"https://platform.claude.com/sessions/{session.id}"
    add(ctx, {"type": "markdown", "props": {"text": f"[Session in the Claude Console]({console})"}})

    lead = ctx.catalog.agents[ctx.team.coordinator].name
    set_status(ctx, lead, "running", "reading the input")
    for key in ctx.team.members:
        set_status(ctx, ctx.catalog.agents[key].name, "queued")
    notes: list[str] = []
    notes_id = None

    # The stream only carries events after it opens, so send the kickoff from inside it.
    async with await client.beta.sessions.events.stream(session.id) as stream:
        await client.beta.sessions.events.send(
            session.id,
            events=[{"type": "user.message", "content": [{"type": "text", "text": kickoff(ctx)}]}],
        )
        async for event in stream:
            match event.type:
                case "session.thread_created":
                    set_status(ctx, event.agent_name, "running", "thread started")
                case "agent.thread_message_sent":
                    set_status(ctx, event.to_agent_name, "running", "working on its brief")
                case "agent.thread_message_received":
                    set_status(ctx, event.from_agent_name, "done", "reported back")
                case "agent.tool_use":
                    set_status(ctx, lead, "running", f"tool: {event.name}")
                case "agent.message":
                    text = "".join(getattr(b, "text", "") or "" for b in event.content)
                    if not text.strip():
                        continue
                    notes.append(text)
                    block = {
                        "type": "markdown",
                        "title": lead,
                        "agent": ctx.team.coordinator,
                        "props": {"text": "\n\n".join(notes)},
                    }
                    if notes_id:
                        update(ctx, notes_id, block)
                    else:
                        notes_id = add(ctx, block)
                case "session.status_terminated":
                    break
                case "session.status_idle":
                    # Idle with requires_action waits on us; any other idle is the end.
                    if event.stop_reason.type != "requires_action":
                        break

    set_status(ctx, lead, "running", "collecting files")
    await asyncio.sleep(FILES_DELAY)
    page = await client.beta.files.list(scope_id=session.id, betas=BETAS)
    for f in page.data:
        add(
            ctx,
            {
                "type": "file",
                "title": "Deliverable",
                "agent": ctx.team.coordinator,
                "props": {
                    "filename": f.filename,
                    "url": f"/api/files/{f.id}?name={quote(f.filename)}",
                },
            },
        )
    set_status(ctx, lead, "done", f"{len(page.data)} file(s)")

"""HTTP API: the agent catalog, canvases, and team runs that fill them.

POST /api/teams/{key}/runs makes a canvas and starts the team in the
background; the page then follows GET /api/canvases/{id}/stream.
"""

import asyncio
import logging
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from anthropic import AsyncAnthropic
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

from . import dummy, runs, store
from .canvas import Canvas
from .canvas import store as canvases
from .canvas.models import block_input_adapter
from .canvas.tools import TOOLS, dispatch
from .catalog import CATALOG, AgentSpec, Catalog, CatalogError, load_catalog

log = logging.getLogger(__name__)

# "managed" runs teams on Claude Managed Agents; "dummy" fills the canvas
# without a model, for local runs and tests.
ORCHESTRATOR = os.environ.get("ORCHESTRATOR", "managed")
# Cloudflare drops a response that sends nothing for 100 seconds.
PING_SECONDS = 20

app = FastAPI()
# Runs outlive the request that started them; keep a reference so they finish.
tasks: set[asyncio.Task] = set()


def catalog() -> Catalog:
    # Read on every request so catalog edits show without a restart.
    try:
        return load_catalog(CATALOG)
    except CatalogError as e:
        raise HTTPException(500, f"invalid catalog: {e}") from e


class AgentOut(BaseModel):
    key: str
    name: str
    description: str
    model: str
    skills: list[str]
    web: bool
    tags: list[str]
    system: str

    @classmethod
    def of(cls, spec: AgentSpec) -> "AgentOut":
        return cls(**spec.model_dump(exclude={"tools"}), web=spec.tools.web)


class TeamSummary(BaseModel):
    key: str
    name: str
    description: str
    coordinator: str
    members: list[str]


class TeamDetail(TeamSummary):
    coordinator_agent: AgentOut
    member_agents: list[AgentOut]
    input_label: str
    sample_input: str | None


class CanvasCreate(BaseModel):
    title: str
    team: str | None = None


class RunRequest(BaseModel):
    input: str | None = None  # defaults to the team's sample input


SUMMARY = {"key", "name", "description", "coordinator", "members"}


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "swarm": bool(runs.swarm().get("agents"))}


@app.get("/api/schema")
def block_schema() -> dict[str, Any]:
    """JSON Schema of every block type the frontend knows how to render."""
    return block_input_adapter.json_schema()


@app.get("/api/tools")
def tool_definitions() -> list[dict[str, Any]]:
    """Canvas tools in Claude custom-tool format, ready to attach to an agent."""
    return TOOLS


@app.get("/api/agents")
def list_agents() -> list[AgentOut]:
    return [AgentOut.of(a) for a in catalog().agents.values()]


@app.get("/api/teams")
def list_teams() -> list[TeamSummary]:
    return [TeamSummary(**t.model_dump(include=SUMMARY)) for t in catalog().teams.values()]


@app.get("/api/teams/{team_key}")
def get_team(team_key: str) -> TeamDetail:
    cat = catalog()
    if team_key not in cat.teams:
        raise HTTPException(404, f"unknown team: {team_key}")
    t = cat.teams[team_key]
    return TeamDetail(
        **t.model_dump(include=SUMMARY),
        coordinator_agent=AgentOut.of(cat.agents[t.coordinator]),
        member_agents=[AgentOut.of(cat.agents[m]) for m in t.members],
        input_label=t.input.label,
        sample_input=cat.read_knowledge(t.input.sample) if t.input.sample else None,
    )


@app.get("/api/canvases")
def list_canvases() -> list[Canvas]:
    return canvases.all_canvases()


@app.post("/api/canvases", status_code=201)
def create_canvas(body: CanvasCreate) -> Canvas:
    return canvases.create(body.title, body.team)


@app.get("/api/canvases/{canvas_id}")
def get_canvas(canvas_id: int) -> Canvas:
    return canvases.get(canvas_id)


@app.post("/api/canvases/{canvas_id}/tools/{tool_name}")
def call_tool(canvas_id: int, tool_name: str, body: dict[str, Any]) -> dict[str, Any]:
    """Run one canvas tool. Same code path an in-process orchestrator uses."""
    return dispatch(canvas_id, tool_name, body)


@app.get("/api/canvases/{canvas_id}/stream")
def stream_canvas(canvas_id: int) -> StreamingResponse:
    """Server-sent events: the full canvas on connect and after every change."""
    canvases.get(canvas_id)  # 404 before the stream starts

    def events() -> Iterator[str]:
        seen, last, quiet = store.tick(), None, False
        while True:
            try:
                canvas = canvases.get(canvas_id)
            except HTTPException:
                return
            if (canvas.version, canvas.title) != last:
                last = (canvas.version, canvas.title)
                yield f"data: {canvas.model_dump_json()}\n\n"
            elif quiet:
                yield ": ping\n\n"
            tick = store.wait(seen, PING_SECONDS)
            quiet, seen = tick == seen, tick

    return StreamingResponse(
        events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"}
    )


@app.post("/api/teams/{team_key}/runs", status_code=202)
async def start_run(team_key: str, body: RunRequest) -> dict:
    cat = catalog()
    if team_key not in cat.teams:
        raise HTTPException(404, f"unknown team: {team_key}")
    team = cat.teams[team_key]
    text = body.input or (cat.read_knowledge(team.input.sample) if team.input.sample else "")
    if not text:
        raise HTTPException(422, "input is required for this team")

    canvas = canvases.create(f"{team.name} run", team=team.key)
    ctx = runs.RunContext(
        catalog=cat,
        team=team,
        input_text=text,
        canvas_id=canvas.id,
        call_tool=lambda name, args: dispatch(canvas.id, name, args),
    )

    async def work() -> None:
        try:
            if ORCHESTRATOR == "dummy":
                await asyncio.to_thread(dummy.DummyOrchestrator().run, ctx)
            else:
                await runs.managed(ctx)
        except Exception as e:
            log.exception("run %s failed", canvas.id)
            runs.add(
                ctx,
                {
                    "type": "callout",
                    "title": "Run failed",
                    "props": {"tone": "danger", "text": str(e)},
                },
            )

    task = asyncio.create_task(work())
    tasks.add(task)
    task.add_done_callback(tasks.discard)
    return {"canvas_id": canvas.id}


@app.get("/api/files/{file_id}")
async def download(file_id: str, name: str = "download") -> Response:
    content = await AsyncAnthropic().beta.files.download(file_id)
    return Response(
        await content.read(),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{Path(name).name}"'},
    )

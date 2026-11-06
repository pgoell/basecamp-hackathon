"""HTTP API consumed by the frontend (and by remote agent runtimes)."""

from __future__ import annotations

import logging
import threading
from collections.abc import Iterator
from functools import lru_cache
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ValidationError

from .. import __version__
from ..agents import RunContext, get_orchestrator
from ..canvas import Canvas, CanvasNotFoundError, CanvasStore, VersionConflictError
from ..canvas.models import block_input_adapter
from ..canvas.store import BlockNotFoundError
from ..canvas.tools import TOOLS, UnknownToolError, dispatch
from ..catalog import AgentSpec, Catalog, CatalogError, load_catalog
from ..config import Settings, get_settings

log = logging.getLogger(__name__)

app = FastAPI(title="Agent Platform", version=__version__)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -- dependencies ------------------------------------------------------------
def get_catalog(settings: Settings = Depends(get_settings)) -> Catalog:
    # Re-read on every request so catalog edits show up without a restart.
    try:
        return load_catalog(settings.catalog_dir)
    except CatalogError as e:
        raise HTTPException(500, f"invalid catalog: {e}") from e


@lru_cache
def get_store() -> CanvasStore:
    return CanvasStore(get_settings().state_dir)


# -- schemas -----------------------------------------------------------------
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
    def of(cls, spec: AgentSpec) -> AgentOut:
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


class RunStarted(BaseModel):
    canvas_id: str


# -- errors ------------------------------------------------------------------
def _tool_errors(fn):
    try:
        return fn()
    except CanvasNotFoundError as e:
        raise HTTPException(404, f"canvas not found: {e}") from e
    except BlockNotFoundError as e:
        raise HTTPException(404, f"block not found: {e}") from e
    except UnknownToolError as e:
        raise HTTPException(404, f"unknown tool: {e}") from e
    except VersionConflictError as e:
        raise HTTPException(
            409, {"message": str(e), "expected": e.expected, "actual": e.actual}
        ) from e
    except ValidationError as e:
        raise HTTPException(422, e.errors(include_url=False)) from e


# -- meta --------------------------------------------------------------------
@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.get("/api/schema")
def block_schema() -> dict[str, Any]:
    """JSON Schema of every block type the frontend knows how to render."""
    return block_input_adapter.json_schema()


@app.get("/api/tools")
def tool_definitions() -> list[dict[str, Any]]:
    """Canvas tools in Claude custom-tool format, ready to attach to an agent."""
    return TOOLS


# -- catalog -----------------------------------------------------------------
@app.get("/api/agents", response_model=list[AgentOut])
def list_agents(catalog: Catalog = Depends(get_catalog)) -> list[AgentOut]:
    return [AgentOut.of(a) for a in catalog.agents.values()]


@app.get("/api/teams", response_model=list[TeamSummary])
def list_teams(catalog: Catalog = Depends(get_catalog)) -> list[TeamSummary]:
    return [
        TeamSummary(
            **t.model_dump(include={"key", "name", "description", "coordinator", "members"})
        )
        for t in catalog.teams.values()
    ]


@app.get("/api/teams/{team_key}", response_model=TeamDetail)
def get_team(team_key: str, catalog: Catalog = Depends(get_catalog)) -> TeamDetail:
    if team_key not in catalog.teams:
        raise HTTPException(404, f"unknown team: {team_key}")
    t = catalog.teams[team_key]
    return TeamDetail(
        **t.model_dump(include={"key", "name", "description", "coordinator", "members"}),
        coordinator_agent=AgentOut.of(catalog.agents[t.coordinator]),
        member_agents=[AgentOut.of(catalog.agents[m]) for m in t.members],
        input_label=t.input.label,
        sample_input=catalog.read_knowledge(t.input.sample) if t.input.sample else None,
    )


# -- canvases ----------------------------------------------------------------
@app.get("/api/canvases", response_model=list[Canvas])
def list_canvases(store: CanvasStore = Depends(get_store)) -> list[Canvas]:
    return store.all()


@app.post("/api/canvases", response_model=Canvas, status_code=201)
def create_canvas(body: CanvasCreate, store: CanvasStore = Depends(get_store)) -> Canvas:
    return store.create(body.title, body.team)


@app.get("/api/canvases/{canvas_id}", response_model=Canvas)
def get_canvas(canvas_id: str, store: CanvasStore = Depends(get_store)) -> Canvas:
    return _tool_errors(lambda: store.get(canvas_id))


@app.post("/api/canvases/{canvas_id}/tools/{tool_name}")
def call_tool(
    canvas_id: str,
    tool_name: str,
    body: dict[str, Any],
    store: CanvasStore = Depends(get_store),
) -> dict[str, Any]:
    """Run one canvas tool. Same code path an in-process orchestrator uses."""
    return _tool_errors(lambda: dispatch(store, canvas_id, tool_name, body))


@app.get("/api/canvases/{canvas_id}/stream")
def stream_canvas(canvas_id: str, store: CanvasStore = Depends(get_store)) -> StreamingResponse:
    """Server-Sent Events: the full canvas on connect and after every change."""
    first = _tool_errors(lambda: store.get(canvas_id))

    def events() -> Iterator[str]:
        canvas = first
        yield f"data: {canvas.model_dump_json()}\n\n"
        last_seen = (canvas.version, canvas.title)
        while True:
            try:
                canvas = store.wait_for_change(canvas_id, canvas.version, timeout=15)
            except CanvasNotFoundError:
                return
            if (canvas.version, canvas.title) == last_seen:
                yield ": keep-alive\n\n"
                continue
            last_seen = (canvas.version, canvas.title)
            yield f"data: {canvas.model_dump_json()}\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# -- runs --------------------------------------------------------------------
@app.post("/api/teams/{team_key}/runs", response_model=RunStarted, status_code=202)
def start_run(
    team_key: str,
    body: RunRequest,
    catalog: Catalog = Depends(get_catalog),
    store: CanvasStore = Depends(get_store),
    settings: Settings = Depends(get_settings),
) -> RunStarted:
    """Create a canvas for the run and start the orchestrator in the background.

    The client then subscribes to ``/api/canvases/{canvas_id}/stream``.
    """
    if team_key not in catalog.teams:
        raise HTTPException(404, f"unknown team: {team_key}")
    team = catalog.teams[team_key]
    text = body.input or (catalog.read_knowledge(team.input.sample) if team.input.sample else "")
    if not text:
        raise HTTPException(422, "input is required for this team")

    canvas = store.create(f"{team.name} run", team=team.key)
    ctx = RunContext(
        catalog=catalog,
        team=team,
        input_text=text,
        canvas_id=canvas.id,
        call_tool=lambda name, args: dispatch(store, canvas.id, name, args),
    )
    orchestrator = get_orchestrator(settings.orchestrator)

    def work() -> None:
        try:
            orchestrator.run(ctx)
        except Exception as e:
            log.exception("run %s failed", canvas.id)
            current = store.get(canvas.id)
            dispatch(
                store,
                canvas.id,
                "add_block",
                {
                    "version": current.version,
                    "block": {
                        "type": "callout",
                        "title": "Run failed",
                        "props": {"tone": "danger", "text": str(e)},
                    },
                },
            )

    threading.Thread(target=work, name=f"run-{canvas.id}", daemon=True).start()
    return RunStarted(canvas_id=canvas.id)

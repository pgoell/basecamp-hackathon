# Backend — agent-platform

Python 3.12 · FastAPI · [uv](https://docs.astral.sh/uv/).

Two parts:

1. **Agent catalog** (`catalog/`): agents and teams as editable files. *Scaffold
   only*: the runtime that executes them is not implemented yet (see
   [`src/agent_platform/agents`](src/agent_platform/agents/__init__.py)).
2. **Canvas** (`src/agent_platform/canvas`): the shared, versioned state that
   agents write through tools and the frontend renders live.

## Agent catalog

```
catalog/
├── agents/<key>/agent.yaml   # name, description, model, skills, tools.web, tags
├── agents/<key>/system.md    # system prompt
├── skills/<key>/SKILL.md     # custom skills
├── teams/<key>.yaml          # coordinator + members + kickoff + budget
└── knowledge/                # sample inputs / context documents
```

Each agent is defined **once** and referenced by key from any team.
`legal-reviewer` and `critic`, for example, serve both `deal-desk` and
`legal-review`. Add an expert by creating `agents/<key>/{agent.yaml,system.md}`
and listing it under a team's `members:`. Run `uv run agent-platform validate`
to check the references.

## Agent runtime (scaffold)

`agents/base.py` defines the contract:

```python
class Orchestrator(Protocol):
    def run(self, ctx: RunContext) -> None: ...  # ctx.call_tool(name, input) -> result
```

`DummyOrchestrator` (the default, `ORCHESTRATOR=dummy`) fakes a run by writing
every block type to the canvas, without calling any model. A real implementation
should attach `canvas.tools.TOOLS` to its coordinator agent and pass each tool
call to `ctx.call_tool`, then be registered in `agents.get_orchestrator`.

## Canvas: how agents change what the UI shows

A canvas is `{id, title, version, blocks[]}`; each block is
`{id, type, title, agent, props}` and `type` picks a frontend component
(`markdown`, `status`, `table`, `kv`, `callout`, `file`).

Agents change it only through **tools**: `get_canvas`, `add_block`,
`update_block`, `move_block`, `delete_block`, `set_title`.

- Every write passes the `version` it last saw and gets the new one back.
- A stale version is refused with **409** and nothing is written. Re-read with
  `get_canvas`, re-apply, and write again. Never write an old canvas back.
- `set_title` doesn't bump the version.
- Props are validated against the block's schema (422 on mismatch).

The same tools are reachable in-process (`canvas.tools.dispatch`) and over HTTP
(`POST /api/canvases/{id}/tools/{name}`), so a runtime hosted elsewhere behaves
the same. `uv run agent-platform tools` prints the definitions in the Claude
custom-tool format.

## Develop

```bash
uv sync
uv run agent-platform serve --reload       # API on :8000, docs at /docs
uv run agent-platform list | validate | tools

uv run ruff check . && uv run ruff format --check .   # lint
uv run pytest                                          # tests
```

## Configuration

| Env var | Default | Purpose |
| --- | --- | --- |
| `CATALOG_DIR` | `./catalog` | Agent catalog (mount a volume to edit live) |
| `STATE_DIR` | `./.state` | Persisted canvases |
| `ORCHESTRATOR` | `dummy` | Agent runtime used for team runs |
| `CORS_ORIGINS` | `http://localhost:5173,http://localhost:8080` | Browser origins allowed |

## API

| Method | Path | |
| --- | --- | --- |
| GET | `/api/health` | status + version |
| GET | `/api/schema` | JSON Schema of all block types |
| GET | `/api/tools` | canvas tool definitions |
| GET | `/api/agents` · `/api/teams` · `/api/teams/{key}` | catalog |
| POST | `/api/teams/{key}/runs` | create a canvas, start the orchestrator → `{canvas_id}` |
| GET/POST | `/api/canvases` · GET `/api/canvases/{id}` | canvases |
| POST | `/api/canvases/{id}/tools/{name}` | run one canvas tool (409 on stale version) |
| GET | `/api/canvases/{id}/stream` | SSE: full canvas on connect and on each change |

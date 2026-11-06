# Basecamp: agent teams

Teams of agents on the Claude Messages API, orchestrated in our own code (`backend/rfp_orchestrator`). In the Deal Desk team a coordinator hands an RFP to five specialists (requirements, pricing, legal, technical fit, competitive intel), each with its own skill; every specialist may send out up to three helpers (document analyst, section writer, fact checker). The coordinator turns their answers into a Word document. Each run fills a live canvas in the web app: one status per agent, helpers included. Details: [`backend/ORCHESTRATION.md`](./backend/ORCHESTRATION.md).

Live at https://basecamp.pgoell.com (shared password; ask Pascal).

## Layout

```
backend/    Python, FastAPI.
  catalog/           agents (agent.yaml + system.md), teams, skills, knowledge. Edit here.
  rfp_orchestrator/  the engine: agent loops, delegation, limits, workspace, docx output
  app/hierarchy.py   runs a catalog team on the engine and turns its events into canvas blocks
  app/main.py        the API under /api
  app/runs.py        run context and canvas helpers shared by the orchestrators
  app/canvas/        canvas blocks and tools: versioned, a stale write gets 409
  app/store.py       versioned JSON docs in SQLite under DATA_DIR (canvas, slides)
                     run workspaces (inputs/, work/, final/) under DATA_DIR/runs/
frontend/   Bun and React. server.ts serves the page and forwards /api.
  src/blocks/        one component per canvas block type
docs/hackathon/  scenario cards and stretch goals
```

## PowerPointless (slides)

A slide editor at `/slides`: 16:9 slides with text, shapes, images and tables, PDF download, and a chat at the side whose agent (Claude Opus 5.5) edits the deck through tools. Several chats per presentation; no user accounts. Details in [`docs/slides.md`](./docs/slides.md).

```
backend/app/slides/   presentations, uploads, chats, agent tools, PDF (Playwright Chromium)
frontend/src/slides/  list, editor, canvas (react-moveable), chat, print page
```

Data lives in `DATA_DIR` (default `backend/data/`, gitignored): presentations in the shared store `basecamp.db`, pictures in `uploads/`. The PDF needs the frontend running: the backend's Chromium prints `FRONTEND_INTERNAL_URL/print/<id>` (default `http://localhost:3000`). Locally, install Chromium once with `uv run playwright install chromium`.

Parts are ported from blattwerk (pgoell's worksheet editor): the element box, undo, the version check on saves, the plain-word schema errors and the Chromium PDF export.

## Run it locally

You need [uv](https://docs.astral.sh/uv/) and [Bun](https://bun.sh).

Quick start:

```bash
scripts/setup.sh    # uv sync + bun install, creates backend/.env
                    # put your ANTHROPIC_API_KEY in backend/.env
scripts/dev.sh      # backend on :8000 and frontend on :3000; Ctrl+C stops both
scripts/check.sh    # the same checks CI runs on pull requests
```

Or by hand:

```bash
echo 'ANTHROPIC_API_KEY=sk-ant-...' > backend/.env    # gitignored

cd backend
uv sync
set -a; . ./.env; set +a
uv run fastapi dev app/main.py        # http://localhost:8000

cd frontend                            # in a second terminal
bun install
bun dev                                # http://localhost:3000
```

Runs use `ORCHESTRATOR=hierarchy` (the default) and need `ANTHROPIC_API_KEY`. `ORCHESTRATOR=dummy` fills the canvas without calling a model. `docker compose up --build` runs both images on the same ports with the dummy. One team in the terminal, without the web app: `uv run python -m app.hierarchy deal-desk`.

Check the backend with `uv run ruff check . && uv run python -m app.catalog && uv run pytest`.

## Change the agents

Edit `backend/catalog/`: an agent is `agents/<key>/agent.yaml` plus `system.md`, a team is `teams/<key>.yaml` naming a coordinator, members and helpers. One agent can serve several teams. There is no setup step: the next run reads the catalog. Limits of the tree (children per specialist, total agents, parallel requests) are set in `rfp_orchestrator/config.py` or by env var, see ORCHESTRATION.md.

## Deploy

Every push to `main` deploys. The **deploy** workflow runs on a runner on the server: it builds both images, pushes them to GHCR and restarts the containers. The compose file, the env file and the Caddy route live in the server-infra repo.

Pull requests run **check** on GitHub's own runners: ruff, the catalog check and pytest for the backend; tsc and the build for the frontend.

## Pick a scenario card

Three cards in [`docs/scenario-cards.md`](./docs/hackathon/scenario-cards.md). Each gives you a coordinator and a different roster of specialists. Different teams should pick different cards.

## Stretch goals

See [`docs/stretch-goals.md`](./docs/hackathon/stretch-goals.md):

- **Custom firm-voice skill**: codify your own firm's voice
- **Critic sub-agent**: a fifth agent that reviews the coordinator's draft before it ships (uncomment `critic` in `backend/catalog/teams/deal-desk.yaml`)
- **Memory across deals**: the coordinator remembers past wins and reuses the right ones
- **Synthetic MCP for past wins**: wire a fake CRM to the pricing specialist

## Demo

Start a run in the web app and narrate the canvas: each specialist's status moves from queued to running to done, the coordinator's notes fill in, and the Word document shows up as a file block when the team finishes.

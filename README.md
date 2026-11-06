# Basecamp: agent teams

Teams of agents on [Claude Managed Agents](https://platform.claude.com/docs/en/managed-agents/multi-agent). In the Deal Desk team a coordinator hands an RFP to four specialists (pricing, legal, technical fit, competitive intel), each with its own skill, and turns their answers into a Word document. Each run fills a live canvas in the web app.

Live at https://basecamp.pgoell.com (shared password; ask Pascal).

## Layout

```
backend/    Python, FastAPI.
  catalog/           agents (agent.yaml + system.md), teams, skills, knowledge. Edit here.
  app/setup.py       creates or updates every team's agents, writes swarm.json
  app/main.py        the API under /api
  app/runs.py        runs a team and turns its session events into canvas blocks
  app/canvas/        canvas blocks and tools: versioned, a stale write gets 409
  app/store.py       versioned JSON docs in SQLite under DATA_DIR (canvas, slides)
  swarm.json         agent and environment ids by catalog key (not secret, committed)
frontend/   Bun and React. server.ts serves the page and forwards /api.
  src/blocks/        one component per canvas block type
docs/hackathon/  scenario cards and stretch goals
```

## Run it locally

You need [uv](https://docs.astral.sh/uv/) and [Bun](https://bun.sh).

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

The backend uses the agents in `backend/swarm.json`, which the whole team shares. `ORCHESTRATOR=dummy` fills the canvas without calling a model. `docker compose up --build` runs both images on the same ports with the dummy.

Check the backend with `uv run ruff check . && uv run python -m app.catalog && uv run pytest`.

## Change the agents

Edit `backend/catalog/`: an agent is `agents/<key>/agent.yaml` plus `system.md`, a team is `teams/<key>.yaml` naming a coordinator and members. One agent can serve several teams. Then either:

- run `uv run python -m app.setup` in `backend/` and commit `swarm.json` if it changed, or
- start the **setup-agents** workflow on GitHub (Actions tab). It runs the same script with the team's key, commits `swarm.json` and deploys.

Setup updates the agents in place, so their ids stay the same. Delete an entry from `swarm.json` to get a fresh one.

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

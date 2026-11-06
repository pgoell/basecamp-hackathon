# basecamp-hackathon: multi-agent platform

Teams of AI agents (a coordinator plus specialists such as Legal, Pricing and
Critic) work on an input. Their results appear live in a web UI whose layout
the agents control.

```
┌──────────────┐  canvas tools (versioned)  ┌──────────────┐  SSE snapshots  ┌──────────────┐
│ Orchestrator │ ─────────────────────────▶ │   Backend    │ ──────────────▶ │   Frontend   │
│  + experts   │   add_block / update_…     │ canvas state │                 │ block→component│
└──────────────┘                            └──────────────┘                 └──────────────┘
```

| Folder | What | Stack |
| --- | --- | --- |
| [`backend/`](backend) | agent catalog, canvas state + tools, HTTP API | Python 3.12, FastAPI, uv |
| [`frontend/`](frontend) | team picker + live canvas renderer | TypeScript, React, Vite, nginx |
| [`docs/hackathon/`](docs/hackathon) | original scenario cards and stretch goals | |

The agent runtime is a **scaffold**: a `DummyOrchestrator` fills the canvas so
the UI and the contract can be developed. See
[backend/README.md](backend/README.md#agent-runtime-scaffold) for the interface a
real orchestrator implements.

## Run locally

```bash
docker compose up --build          # UI: http://localhost:8080 · API: http://localhost:8000/docs
```

Or without Docker: `cd backend && uv sync && uv run agent-platform serve --reload`,
and in another terminal `cd frontend && npm ci && npm run dev` (http://localhost:5173).

## Versioning & releases

Backend and frontend are versioned **independently** with
[Semantic Versioning](https://semver.org), managed by
[release-please](https://github.com/googleapis/release-please):

1. Write [Conventional Commits](https://www.conventionalcommits.org). CI checks
   PR titles, which become the squash-merge commit. `fix:` bumps the patch,
   `feat:` the minor, and `feat!:` / `BREAKING CHANGE:` the major (before 1.0.0,
   breaking changes bump the minor). The component is decided by which folder
   the commit touches.
2. On `main`, release-please keeps a release PR per component that bumps
   `backend/pyproject.toml` + `uv.lock` or `frontend/package.json` and updates its
   `CHANGELOG.md`.
3. Merging it tags `backend-vX.Y.Z` / `frontend-vX.Y.Z`, creates a GitHub
   release, and publishes the image to GHCR:

```
ghcr.io/pgoell/basecamp-hackathon/backend:X.Y.Z   (+ X.Y, X, latest)
ghcr.io/pgoell/basecamp-hackathon/frontend:X.Y.Z
```

Current versions live in [`.release-please-manifest.json`](.release-please-manifest.json).

## CI

[`ci.yml`](.github/workflows/ci.yml) runs on every PR and push to `main`:

- **backend**: `uv lock --check`, ruff lint + format check, catalog validation, pytest
- **frontend**: eslint, `tsc`, prettier check, production build
- **dockerfiles**: hadolint + image build for both (no push)
- **pr-title**: Conventional Commit format

[`release.yml`](.github/workflows/release.yml) runs release-please and calls
[`docker-publish.yml`](.github/workflows/docker-publish.yml) for each released
component. The publish workflow can also be run by hand to republish a tag.

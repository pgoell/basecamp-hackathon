# Hierarchical agent orchestration

Teams from `catalog/` run on the Claude Messages API. The orchestration, its
limits and the event stream are our own code; the limits are **enforced in
code**, not only requested in prompts.

```
Coordinator (team.coordinator, depth 0)  -> any number of members, in parallel
 └─ Members (team.members, depth 1)       -> each up to 3 helpers
     └─ Helpers (team.helpers, depth 2)   -> no delegation
```

Deal Desk: Deal Desk Senior Partner (Opus 5.5) → Requirements Analyst, Pricing,
Legal, Technical Fit, Competitive Intel (Sonnet 5.5) → Document Analyst,
Section Writer, Fact Checker (Haiku 5.5).

## Pieces

| Where | What |
|---|---|
| `rfp_orchestrator/runtime.py` | One tool-use loop per agent, own context window. `delegate(agent, task)` is a client-side tool: the runtime starts the child loop and returns its final report as the tool result. Several `delegate` calls in one turn run concurrently. |
| `rfp_orchestrator/config.py` | `Limits`: depth, children per level, total agents, concurrent requests, turns. |
| `rfp_orchestrator/workspace.py` | Per run: `inputs/` (read-only), `work/` (shared scratch), `final/` (deliverables), `events.jsonl`. |
| `rfp_orchestrator/output.py` | `write_final_document`: markdown → `.md` + branded `.docx`. |
| `app/hierarchy.py` | Builds the roster from the catalog, runs it, and turns events into canvas blocks: a status per agent (helpers show "for <member>"), the coordinator's notes, file blocks, run facts. |
| `app/main.py` | `POST /api/teams/{key}/runs` (as before); files under `GET /api/runs/{canvas_id}/files/{final|work}/...`. |

Run workspaces live under `DATA_DIR/runs/canvas-<id>/`.

## Limits

| Limit | Default | Env |
|---|---|---|
| Max depth | 2 | `RFP_MAX_DEPTH` |
| Children of the coordinator | unlimited | `RFP_MAX_CHILDREN_COORDINATOR` |
| Children per member | 3 | `RFP_MAX_CHILDREN_SPECIALIST` |
| Agents per run | 40 | `RFP_MAX_TOTAL_AGENTS` |
| Parallel API requests per run | 8 | `RFP_MAX_CONCURRENT_REQUESTS` |
| Parallel runs per server | 2 | `MAX_PARALLEL_RUNS` |

## Model settings

- Model per agent from `agent.yaml`; `effort` optional there (default: coordinator
  `high`, members `medium`, helpers `low`).
- Adaptive thinking, automatic prompt caching, streaming.
- Opus/Sonnet requests use server-side refusal fallbacks (`fallbacks: "default"`,
  beta `server-side-fallback-2026-07-01`); off with `Orchestration(use_fallbacks=False)`.
- Custom skills (`catalog/skills/*/SKILL.md`) are injected into the agent's system
  prompt. Anthropic pre-built skills (`docx`, ...) are skipped: documents are
  rendered by `write_final_document`.

## Try it

```bash
cd backend
uv run python -m app.hierarchy deal-desk --show-text   # one run in the terminal
uv run pytest -q                                       # offline, scripted fake client
```

"""Hierarchical team runs on the Claude Messages API (engine: ``rfp_orchestrator``).

The team's coordinator delegates to its members; every member may send out up
to three of the team's helpers. Limits are enforced in code
(``rfp_orchestrator.config.Limits``). Progress lands on the run's canvas: one
status block per agent (helpers included), the coordinator's notes, the
deliverables, and a summary.

Run one team from the terminal, without the web app::

    uv run python -m app.hierarchy deal-desk
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import quote

from rfp_orchestrator import AgentSpec, Event, Limits, RunResult, run_team

from . import store
from .catalog import Catalog, TeamSpec
from .runs import RunContext, add, set_node, update

RUNS_DIR = Path(os.environ.get("RUNS_DIR", store.DATA / "runs"))
FILE_AREAS = ("final", "work")
DEFAULT_EFFORT = {0: "high", 1: "medium", 2: "low"}


def run_dir(canvas_id: int) -> Path:
    return RUNS_DIR / f"canvas-{canvas_id}"


def file_url(canvas_id: int, rel_path: str) -> str:
    return f"/api/runs/{canvas_id}/files/{quote(rel_path)}"


# ---- catalog -> engine roster ---------------------------------------------- #
def build_roster(catalog: Catalog, team: TeamSpec) -> dict[str, AgentSpec]:
    def spec(key: str, depth: int, delegates: list[str]) -> AgentSpec:
        agent = catalog.agents[key]
        skills = tuple(
            (name, (catalog.skills[name].path / "SKILL.md").read_text(encoding="utf-8"))
            for name in agent.skills
            if catalog.skills[name].source == "custom"  # docx & co: we render documents ourselves
        )
        return AgentSpec(
            key=key,
            name=agent.name,
            description=agent.description,
            model=agent.model,
            system=agent.system,
            effort=agent.effort or DEFAULT_EFFORT[depth],
            skills=skills,
            can_delegate_to=tuple(delegates),
            can_write_final=depth == 0,
        )

    # A lead (an agent with members) delegates to its own crew; every other
    # member may send out the team's helpers.
    roster = {team.coordinator: spec(team.coordinator, 0, team.members)}
    for key in team.members:
        crew = catalog.agents[key].members
        roster[key] = spec(key, 1, crew or team.helpers)
    third = set(team.helpers) | {m for key in team.members for m in catalog.agents[key].members}
    roster |= {key: spec(key, 2, []) for key in sorted(third)}
    return roster


def input_filename(team: TeamSpec) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", team.input.label.lower()).strip("-") or "input"
    return f"{slug}.md"


def build_task(ctx: RunContext) -> tuple[str, dict[str, str]]:
    name = input_filename(ctx.team)
    inputs = {name: ctx.input_text} | {doc: ctx.catalog.read_knowledge(doc) for doc in ctx.team.context}
    refs = ", ".join(f"inputs/{d}" for d in ctx.team.context) or "none"
    source = f" (text extracted from the uploaded PDF {ctx.rfp.filename}, {ctx.rfp.pages} pages)" if ctx.rfp else ""
    task = (
        f"{ctx.team.kickoff.strip()}\n\nThe {ctx.team.input.label} is at inputs/{name}{source}.\n"
        f"Reference material: {refs}."
    )
    return task, inputs


# ---- engine events -> canvas blocks ---------------------------------------- #
class CanvasReporter:
    """Turns engine events into canvas blocks. All calls run on the event loop."""

    def __init__(self, ctx: RunContext) -> None:
        self.ctx = ctx
        self.status: dict[str, str] = {}  # engine agent id -> block id
        self.queued: dict[str, str] = {}  # catalog key -> pre-created "queued" block id
        self.names: dict[str, str] = {}  # engine agent id -> display title
        self.notes: list[str] = []
        self.notes_id: str | None = None
        self.work_files: set[str] = set()
        self.node_of: dict[str, str] = {}  # engine agent id -> org node id

    def start(self) -> None:
        cat, team = self.ctx.catalog, self.ctx.team
        root = team.coordinator
        set_node(self.ctx, root, name=cat.agents[root].name, agent=root, state="queued", detail="reading the input")
        for key in team.members:
            set_node(self.ctx, key, name=cat.agents[key].name, agent=key, parent=root, state="idle", detail=None)
        for key in team.members:
            self.queued[key] = add(self.ctx, self._status_block(cat.agents[key].name, key, "queued"))

    async def __call__(self, e: Event) -> None:
        d = e.data
        if e.type == "agent_started":
            key = self._key(e)
            title = e.agent_name or "?"
            if e.parent_id and e.depth and e.depth >= 2:
                title = f"{title} (for {self.names.get(e.parent_id, 'specialist')})"
            self.names[e.agent_id] = e.agent_name or "?"
            block = self._status_block(title, key, "running", _short(d.get("task", "")))
            self._node_started(e, key, _short(d.get("task", "")))
            # The first instance of a member takes over its queued block.
            if key in self.queued:
                block_id = self.queued.pop(key)
                update(self.ctx, block_id, block)
                self.status[e.agent_id] = block_id
            else:
                self.status[e.agent_id] = add(self.ctx, block)
        elif e.type == "agent_tool_call":
            inp = d.get("input") or {}
            detail = {
                "delegate": f"delegating to {inp.get('agent')}",
                "read_file": f"reading {inp.get('path')}",
                "write_work_file": f"writing {inp.get('path')}",
                "list_files": "looking at the workspace",
                "write_final_document": "writing the deliverable",
            }.get(d.get("tool"), d.get("tool"))
            self._set(e, "running", detail)
        elif e.type == "delegation_rejected":
            self._set(e, "running", f"delegation refused: {_short(d.get('reason', ''), 80)}")
        elif e.type == "agent_finished":
            tokens = (d.get("usage") or {}).get("output_tokens", 0)
            detail = f"{d.get('turns')} turns · {d.get('duration_s', 0):.0f}s · {tokens:,} output tokens"
            self._set(e, "done" if d.get("ok") else "failed", detail)
        elif e.type == "agent_error":
            self._set(e, "failed", _short(d.get("error", ""), 120))
        elif e.type == "agent_text" and e.depth == 0:
            self.notes.append(d.get("text", ""))
            block = {
                "type": "markdown",
                "title": self.ctx.catalog.agents[self.ctx.team.coordinator].name,
                "agent": self.ctx.team.coordinator,
                "props": {"text": "\n\n".join(self.notes)},
            }
            if self.notes_id:
                update(self.ctx, self.notes_id, block)
            else:
                self.notes_id = add(self.ctx, block)
        elif e.type == "file_written":
            path = d.get("path", "")
            if path.startswith("final/"):
                add(
                    self.ctx,
                    {
                        "type": "file",
                        "title": "Deliverable",
                        "agent": self.ctx.team.coordinator,
                        "props": {"filename": Path(path).name, "url": file_url(self.ctx.canvas_id, path)},
                    },
                )
            else:
                self.work_files.add(path)

    def finish(self, result: RunResult) -> None:
        for key, block_id in self.queued.items():  # members the coordinator never called
            name = self.ctx.catalog.agents[key].name
            update(self.ctx, block_id, self._status_block(name, key, "done", "not needed for this input"))
            set_node(self.ctx, key, state="idle", detail="not needed for this input")
        if self.work_files:
            links = "\n".join(f"- [{p}]({file_url(self.ctx.canvas_id, p)})" for p in sorted(self.work_files))
            add(self.ctx, {"type": "markdown", "title": "Working files", "props": {"text": links}})
        by_depth: dict[int, int] = {}
        for a in result.agents:
            by_depth[a["depth"]] = by_depth.get(a["depth"], 0) + 1
        items = [
            {"label": "Result", "value": "ok" if result.ok else "failed"},
            {"label": "Duration", "value": f"{result.duration_s:.0f}s"},
            {
                "label": "Agents",
                "value": f"{len(result.agents)} (specialists {by_depth.get(1, 0)}, helpers {by_depth.get(2, 0)})",
            },
        ]
        items += [
            {"label": model, "value": f"{u['output_tokens']:,} out · {u['cache_read_input_tokens']:,} cache read"}
            for model, u in result.usage_by_model.items()
        ]
        add(
            self.ctx,
            {"type": "kv", "title": "Run facts", "agent": self.ctx.team.coordinator, "props": {"items": items}},
        )

    # -- helpers --
    def _key(self, e: Event) -> str | None:
        return next((a.key for a in self.ctx.catalog.agents.values() if a.name == e.agent_name), None)

    @staticmethod
    def _status_block(title: str, key: str | None, state: str, detail: str | None = None) -> dict[str, Any]:
        block: dict[str, Any] = {"type": "status", "title": title, "agent": key, "props": {"state": state}}
        if detail:
            block["props"]["detail"] = detail
        return block

    def _node_started(self, e: Event, key: str | None, task: str) -> None:
        """Place an agent in the org tree, under the node of the agent that started it."""
        root = self.ctx.team.coordinator
        if not e.parent_id:
            node_id = root
        elif key in self.ctx.team.members and self.ctx.nodes.get(key, {}).get("state") == "idle":
            node_id = key  # the first instance of a member takes over its bench node
        else:
            node_id = e.agent_id or "?"
        self.node_of[e.agent_id or ""] = node_id
        parent = self.node_of.get(e.parent_id or "") if e.parent_id else None
        if e.parent_id and parent is None:
            parent = root
        set_node(
            self.ctx, node_id, name=e.agent_name or "?", agent=key, parent=parent, state="running", detail=task or None
        )

    def _set(self, e: Event, state: str, detail: str | None) -> None:
        if node_id := self.node_of.get(e.agent_id or ""):
            set_node(self.ctx, node_id, state=state, detail=detail)
        block_id = self.status.get(e.agent_id or "")
        if block_id is None:
            return
        title = e.agent_name or "?"
        if e.depth and e.depth >= 2 and e.parent_id:
            title = f"{title} (for {self.names.get(e.parent_id, 'specialist')})"
        update(self.ctx, block_id, self._status_block(title, self._key(e), state, detail))


def _short(text: str, n: int = 100) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[: n - 1] + "…"


# ---- entry point used by app.main ------------------------------------------ #
async def hierarchical(ctx: RunContext, *, client=None, limits: Limits | None = None) -> RunResult:
    roster = build_roster(ctx.catalog, ctx.team)
    task, inputs = build_task(ctx)
    reporter = CanvasReporter(ctx)
    reporter.start()
    result = await run_team(
        roster=roster,
        root_key=ctx.team.coordinator,
        task=task,
        inputs=inputs,
        workspace_root=run_dir(ctx.canvas_id),
        limits=limits,
        sinks=[reporter],
        run_id=f"canvas-{ctx.canvas_id}",
        client=client,
    )
    reporter.finish(result)
    return result


if __name__ == "__main__":
    import argparse
    import asyncio

    from rfp_orchestrator import ConsoleSink

    from .catalog import CATALOG, load_catalog

    parser = argparse.ArgumentParser(description="Run one catalog team in the terminal.")
    parser.add_argument("team", nargs="?", default="deal-desk")
    parser.add_argument("--input", type=Path, help="Input document (default: the team's sample).")
    parser.add_argument("--show-text", action="store_true")
    args = parser.parse_args()

    cat = load_catalog(CATALOG)
    team = cat.team(args.team)
    text = args.input.read_text() if args.input else cat.read_knowledge(team.input.sample or "")
    task, inputs = build_task(RunContext(catalog=cat, team=team, input_text=text, canvas_id=0, call_tool=lambda *_: {}))
    out = RUNS_DIR / f"cli-{os.getpid()}"
    res = asyncio.run(
        run_team(
            roster=build_roster(cat, team),
            root_key=team.coordinator,
            task=task,
            inputs=inputs,
            workspace_root=out,
            sinks=[ConsoleSink(args.show_text)],
        )
    )
    print("\n" + res.final_text)
    print(f"\nok={res.ok} agents={len(res.agents)} {res.duration_s:.0f}s -> {out}")

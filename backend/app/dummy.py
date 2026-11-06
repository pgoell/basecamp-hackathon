"""A fake orchestrator that exercises every canvas block type. No LLM calls."""

from __future__ import annotations

import re
import time

from .runs import RunContext, set_node

# Lead key -> words in the RFP that make the dummy engage it.
KEYWORDS = {
    "cloud-architect": r"cloud|azure|aws|gcp|region|hosting|infrastructure|kubernetes",
    "data-engineer": r"data|etl|warehouse|lakehouse|pipeline|analytics|bi\b|machine learning",
    "delivery-lead": r"timeline|milestone|go-live|phase|deadline|implementation",
    "competitive-intel": r"competitor|incumbent|alternative|snowflake|databricks",
}
ALWAYS = ("pricing-specialist", "legal-reviewer")


def pick_leads(ctx: RunContext) -> list[tuple[str, str]]:
    """(lead, reason) for every pool lead the RFP text seems to call for."""
    text = ctx.input_text.lower()
    picked = []
    for key in ctx.team.members:
        if key in ALWAYS:
            picked.append((key, "every bid needs commercial and contract terms"))
        elif key in KEYWORDS and (m := re.search(KEYWORDS[key], text)):
            picked.append((key, f"the RFP mentions '{m.group(0)}'"))
    return picked


class DummyOrchestrator:
    def __init__(self, step_seconds: float = 0.6) -> None:
        self.step = step_seconds

    def run(self, ctx: RunContext) -> None:
        if ctx.team.mode == "dynamic":
            return self.run_dynamic(ctx)
        call = ctx.call_tool
        team = ctx.team
        coordinator = ctx.catalog.agents[team.coordinator]

        version = call("get_canvas", {})["version"]

        def add(block: dict) -> str:
            nonlocal version
            result = call("add_block", {"version": version, "block": block})
            version = result["version"]
            return result["block_id"]

        def update(block_id: str, block: dict) -> None:
            nonlocal version
            version = call("update_block", {"version": version, "block_id": block_id, "block": block})["version"]

        add(
            {
                "type": "callout",
                "title": "Dummy run",
                "props": {
                    "tone": "warning",
                    "text": "This canvas was written by the DummyOrchestrator. No model was called.",
                },
            }
        )
        add(
            {
                "type": "markdown",
                "title": "Brief",
                "agent": team.coordinator,
                "props": {
                    "text": f"**{coordinator.name}** received a "
                    f"{team.input.label.lower()} of {len(ctx.input_text):,} characters "
                    f"and is delegating to {len(team.members)} specialists."
                },
            }
        )

        status_ids = {
            key: add(
                {
                    "type": "status",
                    "title": ctx.catalog.agents[key].name,
                    "agent": key,
                    "props": {"state": "queued"},
                }
            )
            for key in team.members
        }

        for key, block_id in status_ids.items():
            name = ctx.catalog.agents[key].name
            update(
                block_id,
                {
                    "type": "status",
                    "title": name,
                    "agent": key,
                    "props": {"state": "running", "detail": "working on its lane"},
                },
            )
            time.sleep(self.step)
            update(
                block_id,
                {
                    "type": "status",
                    "title": name,
                    "agent": key,
                    "props": {"state": "done", "detail": "report sent"},
                },
            )

        add(
            {
                "type": "table",
                "title": "Specialist summary",
                "agent": team.coordinator,
                "props": {
                    "columns": ["Specialist", "Model", "Verdict"],
                    "rows": [
                        [ctx.catalog.agents[k].name, ctx.catalog.agents[k].model, "placeholder"] for k in team.members
                    ],
                },
            }
        )
        add(
            {
                "type": "kv",
                "title": "Run facts",
                "agent": team.coordinator,
                "props": {
                    "items": [
                        {"label": "Team", "value": team.name},
                        {"label": "Coordinator", "value": coordinator.name},
                        {
                            "label": "Budget",
                            "value": f"${team.budget_usd:g}" if team.budget_usd else "-",
                        },
                    ]
                },
            }
        )
        add(
            {
                "type": "file",
                "title": "Deliverable",
                "agent": team.coordinator,
                "props": {"filename": "deliverable.docx", "url": None},
            }
        )

    def run_dynamic(self, ctx: RunContext) -> None:
        """Staff the bid by keyword, then walk the org tree through its states."""
        cat, team = ctx.catalog, ctx.team
        root = team.coordinator

        def add(block: dict) -> str:
            version = ctx.call_tool("get_canvas", {})["version"]
            return ctx.call_tool("add_block", {"version": version, "block": block})["block_id"]

        add(
            {
                "type": "callout",
                "title": "Dummy run",
                "props": {
                    "tone": "warning",
                    "text": "This canvas was written by the DummyOrchestrator. No model was called.",
                },
            }
        )
        source = f"{ctx.rfp.filename} ({ctx.rfp.pages} pages)" if ctx.rfp else f"{len(ctx.input_text):,} characters"
        set_node(ctx, root, name=cat.agents[root].name, agent=root, state="running", detail=f"reading {source}")
        for key in team.members:
            set_node(ctx, key, name=cat.agents[key].name, agent=key, parent=root, state="idle", detail="on the bench")
        time.sleep(self.step)

        picked = pick_leads(ctx)
        skipped = [k for k in team.members if k not in dict(picked)]
        add(
            {
                "type": "table",
                "title": "Staffing plan",
                "agent": root,
                "props": {
                    "columns": ["Lead", "Engaged", "Why"],
                    "rows": [[cat.agents[k].name, "yes", why] for k, why in picked]
                    + [[cat.agents[k].name, "no", "not needed for this RFP"] for k in skipped],
                },
            }
        )
        for key, why in picked:
            set_node(ctx, key, state="queued", detail=why)
            for m in cat.agents[key].members:
                set_node(ctx, f"{key}/{m}", name=cat.agents[m].name, agent=m, parent=key, state="queued", detail=None)
        set_node(ctx, root, detail=f"engaged {len(picked)} leads")

        for key, why in picked:
            set_node(ctx, key, state="running", detail=why)
            for m in cat.agents[key].members:
                set_node(ctx, f"{key}/{m}", state="running", detail="working on its brief")
                time.sleep(self.step / 2)
                set_node(ctx, f"{key}/{m}", state="done", detail="reported back")
            time.sleep(self.step)
            set_node(ctx, key, state="done", detail="reported back")
            add(
                {
                    "type": "markdown",
                    "title": f"{cat.agents[key].name}: report",
                    "agent": key,
                    "props": {"text": f"Placeholder report from **{cat.agents[key].name}** ({why})."},
                }
            )

        add(
            {
                "type": "kv",
                "title": "Run facts",
                "agent": root,
                "props": {
                    "items": [
                        {"label": "Team", "value": team.name},
                        {"label": "Leads engaged", "value": f"{len(picked)} of {len(team.members)}"},
                        {"label": "Budget", "value": f"${team.budget_usd:g}" if team.budget_usd else "-"},
                        {"label": "Per lead", "value": f"${team.lead_budget_usd:g}" if team.lead_budget_usd else "-"},
                    ]
                },
            }
        )
        set_node(ctx, root, state="done", detail="proposal written")
        add(
            {
                "type": "file",
                "title": "Deliverable",
                "agent": root,
                "props": {"filename": "proposal-response.docx", "url": None},
            }
        )

"""A fake orchestrator that exercises every canvas block type. No LLM calls."""

from __future__ import annotations

import time

from .base import RunContext


class DummyOrchestrator:
    def __init__(self, step_seconds: float = 0.6) -> None:
        self.step = step_seconds

    def run(self, ctx: RunContext) -> None:
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
            version = call(
                "update_block", {"version": version, "block_id": block_id, "block": block}
            )["version"]

        add(
            {
                "type": "callout",
                "title": "Dummy run",
                "props": {
                    "tone": "warning",
                    "text": "This canvas was written by the DummyOrchestrator. "
                    "No model was called.",
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
                        [ctx.catalog.agents[k].name, ctx.catalog.agents[k].model, "placeholder"]
                        for k in team.members
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

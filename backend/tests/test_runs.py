"""The dynamic run loop against a fake Managed Agents client: no network."""

import asyncio
from types import SimpleNamespace as NS

from app import runs
from app.canvas import store as canvases
from app.canvas.tools import dispatch
from app.catalog import CATALOG, load_catalog

ORCH = "sesn_orch"


def ev(type_: str, **kw):
    return NS(type=type_, **kw)


def idle(reason: str):
    return ev("session.status_idle", stop_reason=NS(type=reason))


class FakeStream:
    def __init__(self, gen):
        self.gen = gen

    async def __aenter__(self):
        return self.gen

    async def __aexit__(self, *exc):
        return False


class FakeClient:
    def __init__(self):
        self.sent: list[tuple[str, dict]] = []
        self.created: list[dict] = []
        self.results = asyncio.Event()
        cat = load_catalog(CATALOG)
        self.names = {k: a.name for k, a in cat.agents.items()}
        self.beta = NS(
            sessions=NS(create=self.create, events=NS(stream=self.stream, send=self.send)),
            files=NS(list=self.list_files, upload=None),
        )

    async def create(self, **kw):
        self.created.append(kw)
        return NS(id=ORCH if len(self.created) == 1 else f"sesn_{kw['agent']}")

    async def send(self, session_id, events):
        for e in events:
            self.sent.append((session_id, e))
        results = [e for s, e in self.sent if e["type"] == "user.custom_tool_result"]
        if len(results) == 2:
            self.results.set()

    async def list_files(self, **kw):
        return NS(data=[])

    async def stream(self, session_id):
        return FakeStream(self.orchestrator() if session_id == ORCH else self.lead(session_id))

    async def orchestrator(self):
        await asyncio.sleep(0)
        yield ev("agent.message", content=[NS(text="Staffing: cloud and pricing.")])
        for lead in ("cloud-architect", "pricing-specialist"):
            yield ev(
                "agent.custom_tool_use",
                id=f"tu_{lead}",
                name="engage_lead",
                input={"lead": lead, "reason": "needed", "brief": "go"},
            )
        yield idle("requires_action")
        await self.results.wait()
        yield ev("agent.message", content=[NS(text="Proposal written.")])
        yield idle("end_turn")

    async def lead(self, session_id):
        await asyncio.sleep(0)
        if session_id == "sesn_agent_cloud":
            yield ev("session.thread_created", agent_name=self.names["network-engineer"])
            yield ev("agent.thread_message_received", from_agent_name=self.names["network-engineer"])
        yield ev("agent.message", content=[NS(text=f"report from {session_id}")])
        yield idle("end_turn")


def test_dynamic_run_engages_leads_in_child_sessions(monkeypatch):
    monkeypatch.setattr(runs, "FILES_DELAY", 0)
    cat = load_catalog(CATALOG)
    team = cat.teams["rfp-solutioning"]
    canvas = canvases.create("t", team=team.key)
    ctx = runs.RunContext(
        catalog=cat,
        team=team,
        input_text="RFP text",
        canvas_id=canvas.id,
        call_tool=lambda name, args: dispatch(canvas.id, name, args),
    )
    ids = {
        "environment_id": "env",
        "agents": {"rfp-orchestrator": "agent_orch", "cloud-architect": "agent_cloud", "pricing-specialist": "agent_p"},
    }
    client = FakeClient()

    async def go():
        await client.create(agent="agent_orch")
        await asyncio.wait_for(runs.dynamic(ctx, client, ids, ORCH, None), 5)

    asyncio.run(go())

    # One child session per engaged lead, each with the lead budget.
    children = client.created[1:]
    assert {c["agent"] for c in children} == {"agent_cloud", "agent_p"}
    assert all(c["budget"]["max_list_cost"]["amount"] == "800" for c in children)
    # Every engage_lead call got its lead's report back.
    results = {e["custom_tool_use_id"]: e for s, e in client.sent if e["type"] == "user.custom_tool_result"}
    assert "report from sesn_agent_cloud" in results["tu_cloud-architect"]["content"][0]["text"]
    assert not results["tu_pricing-specialist"]["is_error"]
    # The org tree shows the lead's specialist under it, and everyone engaged is done.
    nodes = {n["id"]: n for n in ctx.nodes.values()}
    assert nodes["cloud-architect/network-engineer"]["state"] == "done"
    assert nodes["cloud-architect"]["state"] == "done"
    assert nodes["data-engineer"]["state"] == "idle"
    assert nodes["rfp-orchestrator"]["state"] == "done"


def test_engage_lead_tool_lists_the_pool():
    cat = load_catalog(CATALOG)
    tool = runs.engage_lead_tool(cat, cat.teams["rfp-solutioning"])
    assert tool["input_schema"]["properties"]["lead"]["enum"] == cat.teams["rfp-solutioning"].members
    assert "Network Engineer" in tool["description"]

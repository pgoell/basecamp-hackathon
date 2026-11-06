"""Team runs. Each run gets a canvas, and an orchestrator fills it through the canvas tools.

`managed` runs the team on Claude Managed Agents: it opens the session's event
stream, sends the kickoff, and turns events into canvas blocks (a status per
agent, the coordinator's messages, the files it wrote). The agents themselves
do not touch the canvas yet. `app.dummy` fills a canvas without calling a model.

A static team is one session: the coordinator delegates to its roster.

A dynamic team goes one level deeper than Managed Agents allows in a single
session (an agent with a roster cannot sit on another agent's roster). The
coordinator gets one custom tool, `engage_lead`. Each call opens a child
session on that lead, which may be a coordinator over its own specialists, and
the lead's report goes back as the tool result. The canvas shows the whole
tree in one `org` block.
"""

import asyncio
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import quote

from anthropic import AsyncAnthropic

from .catalog import AgentSpec, Catalog, TeamSpec
from .rfps import Rfp

log = logging.getLogger(__name__)
SWARM_FILE = Path(__file__).resolve().parents[1] / "swarm.json"
BETAS = ["managed-agents-2026-04-01"]
# Files show up in the Files API a few seconds after the session ends.
FILES_DELAY = 3
ENGAGE_LEAD = "engage_lead"
RFP_MOUNT = "/mnt/session/uploads/rfp.pdf"

# (tool_name, tool_input) -> tool_result, bound to one canvas.
CanvasTool = Callable[[str, dict[str, Any]], dict[str, Any]]


@dataclass
class RunContext:
    catalog: Catalog
    team: TeamSpec
    input_text: str
    canvas_id: int
    # The orchestrator's only channel to the UI. Call it as an agent calls a tool:
    # call_tool("add_block", {"version": 3, "block": {...}}).
    call_tool: CanvasTool
    # An uploaded PDF, when the input came as one. input_text then holds its text.
    rfp: Rfp | None = None
    # Status block id per agent name, filled as the run goes.
    status: dict[str, str] = field(default_factory=dict)
    # The org tree of a dynamic run: node id -> node, in insertion order.
    nodes: dict[str, dict] = field(default_factory=dict)
    org_id: str | None = None


def swarm() -> dict:
    return json.loads(SWARM_FILE.read_text()) if SWARM_FILE.exists() else {}


# -- kickoff -------------------------------------------------------------------
def input_doc(ctx: RunContext) -> str:
    if ctx.rfp:
        body = (
            f"(Attached as a PDF document: {ctx.rfp.filename}, {ctx.rfp.pages} pages. "
            f"It is also mounted in the sandbox at {RFP_MOUNT}.)"
        )
    else:
        body = ctx.input_text
    return f"=====  DOCUMENT: {ctx.team.input.label}  =====\n{body}"


def kickoff(ctx: RunContext) -> str:
    docs = [input_doc(ctx)] + [
        f"=====  DOCUMENT: {name}  =====\n{ctx.catalog.read_knowledge(name)}" for name in ctx.team.context
    ]
    return ctx.team.kickoff.strip() + "\n\n" + "\n\n".join(docs)


def content(text: str, ctx: RunContext, file_id: str | None) -> list[dict]:
    """A user.message body: the text, then the RFP PDF when there is one."""
    blocks: list[dict] = [{"type": "text", "text": text}]
    if file_id and ctx.rfp:
        blocks.append({"type": "document", "source": {"type": "file", "file_id": file_id}, "title": ctx.rfp.filename})
    return blocks


def budget(usd: float | None) -> dict:
    """sessions.create kwargs for a hard spend cap, in whole US cents."""
    if not usd:
        return {}
    return {"budget": {"type": "limit", "max_list_cost": {"amount": str(round(usd * 100)), "currency": "USD"}}}


def resources(file_id: str | None) -> dict:
    return {"resources": [{"type": "file", "file_id": file_id, "mount_path": RFP_MOUNT}]} if file_id else {}


async def upload_rfp(client: AsyncAnthropic, ctx: RunContext) -> str | None:
    if not ctx.rfp:
        return None
    made = await client.beta.files.upload(
        file=(ctx.rfp.filename, ctx.rfp.path.read_bytes(), "application/pdf"), betas=BETAS
    )
    return made.id


# -- engage_lead ---------------------------------------------------------------
def engage_lead_tool(catalog: Catalog, team: TeamSpec) -> dict:
    """The custom tool a dynamic team's coordinator uses to staff the bid."""
    lines = []
    for key in team.members:
        agent = catalog.agents[key]
        crew = ", ".join(catalog.agents[m].name for m in agent.members)
        lines.append(f"- {key}: {agent.name}. {agent.description.strip()}" + (f" Runs: {crew}." if crew else ""))
    return {
        "type": "custom",
        "name": ENGAGE_LEAD,
        "description": (
            "Engage one lead on this bid. The lead works in its own session and, if it has a team, "
            "briefs its own specialists in parallel. The tool returns the lead's report as text, which "
            "can take several minutes. Engage only the leads the RFP needs, and call this tool for all "
            "of them in the same turn so they run in parallel. The lead sees none of your conversation: "
            "the brief must carry the requirements it needs. The RFP PDF is attached to its session.\n\n"
            "Leads:\n" + "\n".join(lines)
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "lead": {"type": "string", "enum": list(team.members), "description": "Key of the lead."},
                "reason": {
                    "type": "string",
                    "description": "One line on why this RFP needs this lead. Shown to the user.",
                },
                "brief": {
                    "type": "string",
                    "description": "The relevant requirements, the question, and the answer format.",
                },
            },
            "required": ["lead", "reason", "brief"],
        },
    }


# -- canvas helpers ------------------------------------------------------------
def add(ctx: RunContext, block: dict) -> str:
    version = ctx.call_tool("get_canvas", {})["version"]
    return ctx.call_tool("add_block", {"version": version, "block": block})["block_id"]


def update(ctx: RunContext, block_id: str, block: dict) -> None:
    version = ctx.call_tool("get_canvas", {})["version"]
    ctx.call_tool("update_block", {"version": version, "block_id": block_id, "block": block})


def upsert(ctx: RunContext, block_id: str | None, block: dict) -> str:
    if block_id:
        update(ctx, block_id, block)
        return block_id
    return add(ctx, block)


def set_status(ctx: RunContext, name: str, state: str, detail: str | None = None) -> None:
    key = next((a.key for a in ctx.catalog.agents.values() if a.name == name), None)
    block = {"type": "status", "title": name, "agent": key, "props": {"state": state}}
    if detail:
        block["props"]["detail"] = detail
    if name in ctx.status:
        update(ctx, ctx.status[name], block)
    else:
        ctx.status[name] = add(ctx, block)


def set_node(ctx: RunContext, node_id: str, **fields: Any) -> None:
    """Add or change one node of the org tree and rewrite the org block."""
    node = ctx.nodes.setdefault(node_id, {"id": node_id, "name": node_id, "agent": None, "parent": None})
    node.update(fields)
    block = {
        "type": "org",
        "title": "Bid team",
        "agent": ctx.team.coordinator,
        "props": {"nodes": list(ctx.nodes.values())},
    }
    ctx.org_id = upsert(ctx, ctx.org_id, block)


def message_text(event: Any) -> str:
    return "".join(getattr(b, "text", "") or "" for b in event.content)


async def collect_files(ctx: RunContext, client: AsyncAnthropic, session_id: str) -> int:
    await asyncio.sleep(FILES_DELAY)
    page = await client.beta.files.list(scope_id=session_id, betas=BETAS)
    for f in page.data:
        add(
            ctx,
            {
                "type": "file",
                "title": "Deliverable",
                "agent": ctx.team.coordinator,
                "props": {
                    "filename": f.filename,
                    "url": f"/api/files/{f.id}?name={quote(f.filename)}",
                },
            },
        )
    return len(page.data)


# -- runs ----------------------------------------------------------------------
async def managed(ctx: RunContext) -> None:
    ids = swarm()
    coordinator_id = ids.get("agents", {}).get(ctx.team.coordinator)
    if not coordinator_id:
        raise RuntimeError(f"No agent id for '{ctx.team.coordinator}' in swarm.json. Run the setup-agents workflow.")
    client = AsyncAnthropic()
    file_id = await upload_rfp(client, ctx)
    session = await client.beta.sessions.create(
        agent=coordinator_id,
        environment_id=ids["environment_id"],
        title=f"{ctx.team.name} run",
        **budget(ctx.team.budget_usd),
        **resources(file_id),
    )
    console = f"https://platform.claude.com/sessions/{session.id}"
    add(ctx, {"type": "markdown", "props": {"text": f"[Session in the Claude Console]({console})"}})

    if ctx.team.mode == "dynamic":
        await dynamic(ctx, client, ids, session.id, file_id)
    else:
        await static(ctx, client, session.id, file_id)


async def static(ctx: RunContext, client: AsyncAnthropic, session_id: str, file_id: str | None) -> None:
    lead = ctx.catalog.agents[ctx.team.coordinator].name
    set_status(ctx, lead, "running", "reading the input")
    for key in ctx.team.members:
        set_status(ctx, ctx.catalog.agents[key].name, "queued")
    notes: list[str] = []
    notes_id = None

    # The stream only carries events after it opens, so send the kickoff from inside it.
    async with await client.beta.sessions.events.stream(session_id) as stream:
        await client.beta.sessions.events.send(
            session_id,
            events=[{"type": "user.message", "content": content(kickoff(ctx), ctx, file_id)}],
        )
        async for event in stream:
            match event.type:
                case "session.thread_created":
                    set_status(ctx, event.agent_name, "running", "thread started")
                case "agent.thread_message_sent":
                    set_status(ctx, event.to_agent_name, "running", "working on its brief")
                case "agent.thread_message_received":
                    set_status(ctx, event.from_agent_name, "done", "reported back")
                case "agent.tool_use":
                    set_status(ctx, lead, "running", f"tool: {event.name}")
                case "agent.message":
                    text = message_text(event)
                    if not text.strip():
                        continue
                    notes.append(text)
                    notes_id = upsert(
                        ctx,
                        notes_id,
                        {
                            "type": "markdown",
                            "title": lead,
                            "agent": ctx.team.coordinator,
                            "props": {"text": "\n\n".join(notes)},
                        },
                    )
                case "session.status_terminated":
                    break
                case "session.status_idle":
                    # Idle with requires_action waits on us; any other idle is the end.
                    if event.stop_reason.type != "requires_action":
                        break

    set_status(ctx, lead, "running", "collecting files")
    count = await collect_files(ctx, client, session_id)
    set_status(ctx, lead, "done", f"{count} file(s)")


async def dynamic(ctx: RunContext, client: AsyncAnthropic, ids: dict, session_id: str, file_id: str | None) -> None:
    root = ctx.team.coordinator
    coordinator = ctx.catalog.agents[root]
    set_node(ctx, root, name=coordinator.name, agent=root, state="running", detail="reading the RFP")
    for key in ctx.team.members:
        set_node(
            ctx, key, name=ctx.catalog.agents[key].name, agent=key, parent=root, state="idle", detail="on the bench"
        )

    notes: list[str] = []
    notes_id = None
    pending: set[asyncio.Task] = set()
    engaged = 0

    async def answer(event: Any) -> None:
        nonlocal engaged
        args = event.input or {}
        key = args.get("lead")
        ok = False
        if event.name != ENGAGE_LEAD:
            text = f"Unknown tool '{event.name}'."
        elif key not in ctx.team.members:
            text = f"Unknown lead '{key}'. Pick one of: {', '.join(ctx.team.members)}."
        elif engaged >= ctx.team.max_leads:
            text = f"This run allows at most {ctx.team.max_leads} engagements. Work with the reports you have."
        else:
            engaged += 1
            try:
                text, ok = await run_lead(ctx, client, ids, key, args, file_id)
            except Exception as e:  # never leave the orchestrator waiting on a call
                log.exception("lead %s failed", key)
                text = f"The lead failed: {e}. Continue without it."
        await client.beta.sessions.events.send(
            session_id,
            events=[
                {
                    "type": "user.custom_tool_result",
                    "custom_tool_use_id": event.id,
                    "content": [{"type": "text", "text": text}],
                    "is_error": not ok,
                }
            ],
        )

    try:
        async with await client.beta.sessions.events.stream(session_id) as stream:
            await client.beta.sessions.events.send(
                session_id,
                events=[{"type": "user.message", "content": content(kickoff(ctx), ctx, file_id)}],
            )
            async for event in stream:
                match event.type:
                    case "agent.custom_tool_use":
                        set_node(ctx, root, state="running", detail="waiting on leads")
                        task = asyncio.create_task(answer(event))
                        pending.add(task)
                        task.add_done_callback(pending.discard)
                    case "agent.tool_use":
                        set_node(ctx, root, state="running", detail=f"tool: {event.name}")
                    case "agent.message":
                        text = message_text(event)
                        if not text.strip():
                            continue
                        notes.append(text)
                        notes_id = upsert(
                            ctx,
                            notes_id,
                            {
                                "type": "markdown",
                                "title": coordinator.name,
                                "agent": root,
                                "props": {"text": "\n\n".join(notes)},
                            },
                        )
                    case "session.status_terminated":
                        break
                    case "session.status_idle":
                        # requires_action: our engage_lead answers are still running.
                        if event.stop_reason.type != "requires_action":
                            break
    finally:
        for task in pending:
            task.cancel()

    set_node(ctx, root, state="running", detail="collecting files")
    count = await collect_files(ctx, client, session_id)
    set_node(ctx, root, state="done", detail=f"{count} file(s)")


async def run_lead(
    ctx: RunContext, client: AsyncAnthropic, ids: dict, key: str, args: dict, file_id: str | None
) -> tuple[str, bool]:
    """Run one lead in its own session. Returns (report, ok)."""
    lead = ctx.catalog.agents[key]
    agent_id = ids.get("agents", {}).get(key)
    set_node(ctx, key, state="running", detail=args.get("reason") or "engaged")
    if not agent_id:
        set_node(ctx, key, state="failed", detail="not set up: no id in swarm.json")
        return f"{lead.name} is not set up yet (no agent id). Continue without this lead.", False
    for m in lead.members:
        set_node(ctx, f"{key}/{m}", name=ctx.catalog.agents[m].name, agent=m, parent=key, state="queued", detail=None)

    def sub(name: str | None, state: str, detail: str) -> None:
        if not name or name == lead.name:
            return
        member = next((m for m in lead.members if ctx.catalog.agents[m].name == name), None)
        node_id = f"{key}/{member or name}"
        set_node(ctx, node_id, name=name, agent=member, parent=key, state=state, detail=detail)

    brief = (
        f"Brief from the {ctx.catalog.agents[ctx.team.coordinator].name} on the {ctx.team.name} bid.\n\n"
        f"{args.get('brief', '').strip()}"
    )
    if ctx.rfp and file_id:
        brief += f"\n\nThe full RFP is attached ({ctx.rfp.filename}) and mounted at {RFP_MOUNT}."
    report: list[str] = []
    report_id = None
    try:
        session = await client.beta.sessions.create(
            agent=agent_id,
            environment_id=ids["environment_id"],
            title=f"{ctx.team.name}: {lead.name}",
            **budget(ctx.team.lead_budget_usd),
            **resources(file_id),
        )
        async with await client.beta.sessions.events.stream(session.id) as stream:
            await client.beta.sessions.events.send(
                session.id, events=[{"type": "user.message", "content": content(brief, ctx, file_id)}]
            )
            async for event in stream:
                match event.type:
                    case "session.thread_created":
                        sub(event.agent_name, "running", "thread started")
                    case "agent.thread_message_sent":
                        sub(event.to_agent_name, "running", "working on its brief")
                    case "agent.thread_message_received":
                        sub(event.from_agent_name, "done", "reported back")
                    case "agent.tool_use":
                        set_node(ctx, key, detail=f"tool: {event.name}")
                    case "agent.message":
                        text = message_text(event)
                        if not text.strip():
                            continue
                        report.append(text)
                        report_id = upsert(ctx, report_id, report_block(lead, report))
                    case "session.status_terminated" | "session.status_idle":
                        # Leads have no custom tools, so any idle is the end.
                        break
    except Exception as e:
        set_node(ctx, key, state="failed", detail=str(e)[:200])
        return f"{lead.name} failed: {e}. Continue without this lead.", False

    set_node(ctx, key, state="done", detail="reported back")
    return ("\n\n".join(report) or f"{lead.name} sent no report."), bool(report)


def report_block(lead: AgentSpec, report: list[str]) -> dict:
    return {
        "type": "markdown",
        "title": f"{lead.name}: report",
        "agent": lead.key,
        "props": {"text": "\n\n".join(report)},
    }

"""Chats beside a presentation: each message runs the agent, which edits the deck with tools.

The loop runs as its own task, so a turn finishes and is stored even if the browser leaves.
Each assistant message is stored whole (thinking blocks included) and replayed as it came.
"""

import asyncio
import json
import sqlite3
from typing import Annotated

import anthropic
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.slides import db
from app.slides.presentations import find
from app.slides.tools import TOOLS, ToolError, execute

router = APIRouter(prefix="/api/slides")
Con = Annotated[sqlite3.Connection, Depends(db.con)]
MODEL = "claude-opus-5-5"
PING_SECONDS = 20
SYSTEM = """You edit a slide presentation for the user, as a capable colleague in PowerPoint would.

The deck is JSON you change only through your tools. Slides are 960 x 540 pt (16:9); all \
positions, sizes and font sizes are in pt from the slide's top left. Elements draw in order, the \
last on top.

Call get_presentation before your first change in a turn, and again after a tool reports an \
error. Keep 40 pt clear of the slide edges unless the user wants full-bleed. Titles read best at \
about 40 pt, body text at about 24 pt, with no more than six bullets on a slide. Prefer the \
layouts (add_slide, apply_layout) for title and body text, and keep a deck's colours and fonts \
consistent. For a chart, draw it with shapes and text, or use an image if the user gives one.

Each user message starts with the id of the slide they are looking at, such as \
"[current slide: ab12cd34]". "This slide" means that one. The user sees the deck update as you \
work; when you are done, say in a sentence or two what you changed."""

client = anthropic.AsyncAnthropic()
busy: set[int] = set()


class Send(BaseModel):
    text: str = Field(min_length=1, max_length=20000)
    slide: str | None = None


def chat_row(con: sqlite3.Connection, chat_id: int) -> sqlite3.Row:
    row = con.execute("SELECT * FROM chats WHERE id = ?", (chat_id,)).fetchone()
    if not row:
        raise HTTPException(404)
    return row


def history(con: sqlite3.Connection, chat_id: int) -> list[dict]:
    rows = con.execute("SELECT role, content FROM messages WHERE chat_id = ? ORDER BY id", (chat_id,))
    return [{"role": r["role"], "content": json.loads(r["content"])} for r in rows]


def store(con: sqlite3.Connection, chat_id: int, role: str, content) -> None:
    con.execute(
        "INSERT INTO messages (chat_id, role, content) VALUES (?, ?, ?)",
        (chat_id, role, json.dumps(content)),
    )


@router.get("/presentations/{pid}/chats")
def chats(pid: int, con: Con) -> list[dict]:
    find(con, pid)
    rows = con.execute(
        "SELECT id, presentation_id, title, created FROM chats WHERE presentation_id = ? ORDER BY id DESC",
        (pid,),
    )
    return [dict(r) for r in rows]


@router.post("/presentations/{pid}/chats")
def new_chat(pid: int, con: Con) -> dict:
    find(con, pid)
    row = con.execute(
        "INSERT INTO chats (presentation_id) VALUES (?) RETURNING id, presentation_id, title, created",
        (pid,),
    ).fetchone()
    return dict(row)


@router.get("/chats/{chat_id}")
def chat(chat_id: int, con: Con) -> dict:
    """The chat with its messages. Thinking blocks are left out: the page shows text, tool calls
    and tool results."""
    row = dict(chat_row(con, chat_id))
    shown = []
    for message in history(con, chat_id):
        content = message["content"]
        if isinstance(content, str):
            content = [{"type": "text", "text": content}]
        content = [b for b in content if b.get("type") in ("text", "tool_use", "tool_result")]
        if content:
            shown.append({"role": message["role"], "content": content})
    return {**row, "messages": shown, "busy": chat_id in busy}


@router.delete("/chats/{chat_id}")
def delete_chat(chat_id: int, con: Con) -> dict:
    chat_row(con, chat_id)
    con.execute("DELETE FROM chats WHERE id = ?", (chat_id,))
    return {}


@router.post("/chats/{chat_id}/messages")
async def send(chat_id: int, body: Send, con: Con) -> StreamingResponse:
    row = chat_row(con, chat_id)
    if chat_id in busy:
        raise HTTPException(409, "The agent is still answering in this chat.")
    busy.add(chat_id)
    if not con.execute("SELECT 1 FROM messages WHERE chat_id = ?", (chat_id,)).fetchone():
        con.execute("UPDATE chats SET title = ? WHERE id = ?", (body.text[:60], chat_id))
    note = f"[current slide: {body.slide}]\n" if body.slide else ""
    store(con, chat_id, "user", [{"type": "text", "text": note + body.text}])

    queue: asyncio.Queue[dict | None] = asyncio.Queue()
    task = asyncio.create_task(run(chat_id, row["presentation_id"], queue))
    task.add_done_callback(lambda _: busy.discard(chat_id))

    async def events():
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), PING_SECONDS)
            except TimeoutError:
                yield ": ping\n\n"
                continue
            if item is None:
                break
            yield f"data: {json.dumps(item)}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


async def run(chat_id: int, pid: int, queue: asyncio.Queue) -> None:
    con = db.connect()
    try:
        await loop(con, chat_id, pid, queue.put_nowait)
    except anthropic.APIStatusError as e:
        queue.put_nowait({"type": "error", "message": f"Claude API error {e.status_code}: {e.message}"})
    except anthropic.APIConnectionError:
        queue.put_nowait({"type": "error", "message": "Could not reach the Claude API."})
    except Exception as e:  # report it in the chat rather than dropping the stream
        queue.put_nowait({"type": "error", "message": str(e)})
    finally:
        con.close()
        queue.put_nowait({"type": "done"})
        queue.put_nowait(None)


async def loop(con: sqlite3.Connection, chat_id: int, pid: int, emit) -> None:
    messages = history(con, chat_id)
    retries = 0
    while True:
        try:
            async with client.beta.messages.stream(
                model=MODEL,
                max_tokens=64000,
                thinking={"type": "adaptive"},
                output_config={"effort": "medium"},
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
                system=SYSTEM,
                tools=TOOLS,
                messages=messages,
                # The tools and the history so far are the same prefix each round: cache it.
                cache_control={"type": "ephemeral"},
            ) as stream:
                async for event in stream:
                    if event.type == "text":
                        emit({"type": "text", "text": event.text})
                response = await stream.get_final_message()
            retries = 0
        except ValueError:
            # Tool input the SDK could not parse at all: there is no tool_use id to answer, so
            # the turn goes again, a few times at most. API errors are not ValueError.
            retries += 1
            if retries > 2:
                raise
            continue

        content = [block.model_dump(mode="json", exclude_none=True) for block in response.content]
        if response.stop_reason == "pause_turn":
            store(con, chat_id, "assistant", content)
            messages.append({"role": "assistant", "content": content})
            continue
        uses = [b for b in response.content if b.type == "tool_use"]
        if response.stop_reason == "refusal":
            store(con, chat_id, "assistant", content)
            emit({"type": "error", "message": "Claude declined this request."})
            return
        if not uses:
            store(con, chat_id, "assistant", content)
            return
        if response.stop_reason == "max_tokens":
            # A tool input cut off at the limit parses as a valid partial one: never run it.
            emit({"type": "error", "message": "The answer ran too long and was cut off."})
            return

        results = []
        for use in uses:
            emit({"type": "tool", "name": use.name, "input": use.input})
            try:
                text, version = await asyncio.to_thread(execute, use.name, use.input, pid)
                results.append({"type": "tool_result", "tool_use_id": use.id, "content": text})
                emit({"type": "tool_result", "name": use.name, "ok": True, "text": text[:500]})
                if version is not None:
                    emit({"type": "doc", "version": version})
            except ToolError as e:
                results.append(
                    {"type": "tool_result", "tool_use_id": use.id, "content": str(e), "is_error": True}
                )
                emit({"type": "tool_result", "name": use.name, "ok": False, "text": str(e)[:500]})
        # The assistant turn and its results go in together, so the stored history never holds
        # a tool call without its answer.
        store(con, chat_id, "assistant", content)
        store(con, chat_id, "user", results)
        messages += [{"role": "assistant", "content": content}, {"role": "user", "content": results}]

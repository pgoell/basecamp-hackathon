"""Canvas reads and block changes, kept as docs of kind "canvas" in app.store.

Every block change takes the version the writer last saw. If the canvas has
moved on since, app.store refuses the write with 409 and nothing changes, so an
orchestrator, its specialists and a person in the browser never silently
overwrite each other.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable

from fastapi import HTTPException

from .. import store
from .models import Block, BlockInput, Canvas

KIND = "canvas"


def _canvas(row: dict) -> Canvas:
    return Canvas(
        id=row["id"],
        title=row["title"],
        version=row["version"],
        updated=row["updated"],
        **row["doc"],
    )


def _as_block(block_id: str, block: BlockInput) -> Block:
    return Block(id=block_id, **block.model_dump())


def _index(canvas: Canvas, block_id: str) -> int:
    for i, b in enumerate(canvas.blocks):
        if b.id == block_id:
            return i
    raise HTTPException(404, f"No block with id {block_id}.")


def all_canvases() -> list[Canvas]:
    return [_canvas(r) for r in store.list_all(KIND, with_doc=True)]


def get(canvas_id: int) -> Canvas:
    return _canvas(store.get(canvas_id, KIND))


def create(title: str, team: str | None = None) -> Canvas:
    return _canvas(store.create(KIND, title, {"team": team, "blocks": []}))


def set_title(canvas_id: int, title: str) -> Canvas:
    get(canvas_id)  # 404 on another kind
    return _canvas(store.write(canvas_id, None, title=title))


def _change(canvas_id: int, version: int, fn: Callable[[Canvas], None]) -> Canvas:
    canvas = get(canvas_id)
    fn(canvas)
    doc = canvas.model_dump(mode="json", include={"team", "blocks"})
    return _canvas(store.write(canvas_id, version, doc=doc))


def add_block(
    canvas_id: int, version: int, block: BlockInput, after: str | None = None
) -> tuple[Canvas, str]:
    new = _as_block(f"blk_{uuid.uuid4().hex[:10]}", block)

    def fn(c: Canvas) -> None:
        c.blocks.insert(len(c.blocks) if after is None else _index(c, after) + 1, new)

    return _change(canvas_id, version, fn), new.id


def update_block(canvas_id: int, version: int, block_id: str, block: BlockInput) -> Canvas:
    def fn(c: Canvas) -> None:
        c.blocks[_index(c, block_id)] = _as_block(block_id, block)

    return _change(canvas_id, version, fn)


def move_block(canvas_id: int, version: int, block_id: str, index: int) -> Canvas:
    def fn(c: Canvas) -> None:
        moved = c.blocks.pop(_index(c, block_id))
        c.blocks.insert(max(0, min(index, len(c.blocks))), moved)

    return _change(canvas_id, version, fn)


def delete_block(canvas_id: int, version: int, block_id: str) -> Canvas:
    return _change(canvas_id, version, lambda c: c.blocks.pop(_index(c, block_id)))

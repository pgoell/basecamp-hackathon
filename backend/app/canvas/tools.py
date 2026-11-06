"""Canvas tools: the only way an agent changes what the user sees.

``TOOLS`` holds definitions in the Claude custom-tool shape
(``name`` / ``description`` / ``input_schema``) so they can be attached to the
orchestrator as-is; :func:`dispatch` executes a call. The HTTP endpoint
``POST /api/canvases/{id}/tools/{name}`` goes through the same function, so
an agent runtime hosted elsewhere (or an MCP shim) gets identical behaviour.

Every write takes ``version`` and returns the new one. Errors raise
HTTPException: 404 for an unknown canvas, block or tool, 422 for bad input,
409 for a stale version. On 409 the agent calls ``get_canvas`` and retries;
it never writes an old canvas back.
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel, Field, ValidationError

from . import store
from .models import BlockInput


class GetCanvas(BaseModel):
    """Read the canvas: its title, current version and every block with its id."""


class SetTitle(BaseModel):
    """Rename the canvas. Does not change the version."""

    title: str


class AddBlock(BaseModel):
    """Add a block to the canvas. Returns the new block's id and the new version."""

    version: int = Field(description="The canvas version you last read or wrote.")
    block: BlockInput
    after: str | None = Field(None, description="Insert after this block id; default: end.")


class UpdateBlock(BaseModel):
    """Replace a block's title/props (its type may change too). Keeps the block id."""

    version: int
    block_id: str
    block: BlockInput


class MoveBlock(BaseModel):
    """Move a block to a 0-based position."""

    version: int
    block_id: str
    index: int


class DeleteBlock(BaseModel):
    """Remove a block."""

    version: int
    block_id: str


_TOOL_MODELS: dict[str, type[BaseModel]] = {
    "get_canvas": GetCanvas,
    "set_title": SetTitle,
    "add_block": AddBlock,
    "update_block": UpdateBlock,
    "move_block": MoveBlock,
    "delete_block": DeleteBlock,
}

TOOLS: list[dict[str, Any]] = [
    {
        "name": name,
        "description": (model.__doc__ or "").strip(),
        "input_schema": model.model_json_schema(),
    }
    for name, model in _TOOL_MODELS.items()
]


def dispatch(canvas_id: int, name: str, raw_input: dict) -> dict[str, Any]:
    """Validate and run one tool call against a canvas. Returns a JSON-able result."""
    model = _TOOL_MODELS.get(name)
    if model is None:
        raise HTTPException(404, f"No tool named {name}.")
    try:
        args = model.model_validate(raw_input)
    except ValidationError as e:
        raise HTTPException(422, e.errors(include_url=False, include_context=False)) from e

    match args:
        case GetCanvas():
            return store.get(canvas_id).model_dump(mode="json")
        case SetTitle(title=title):
            canvas = store.set_title(canvas_id, title)
        case AddBlock(version=v, block=block, after=after):
            canvas, block_id = store.add_block(canvas_id, v, block, after)
            return {"version": canvas.version, "block_id": block_id}
        case UpdateBlock(version=v, block_id=bid, block=block):
            canvas = store.update_block(canvas_id, v, bid, block)
        case MoveBlock(version=v, block_id=bid, index=i):
            canvas = store.move_block(canvas_id, v, bid, i)
        case DeleteBlock(version=v, block_id=bid):
            canvas = store.delete_block(canvas_id, v, bid)
    return {"version": canvas.version}

"""Block types. Keep in sync with ``frontend/src/blocks/types.ts``.

Each block is ``{id, type, title, agent, props}``; ``type`` selects the props
schema and the frontend component. ``GET /api/schema`` exports the JSON Schema.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# -- props per block type ----------------------------------------------------
class MarkdownProps(_Strict):
    text: str = Field(description="Markdown body.")


class StatusProps(_Strict):
    state: Literal["queued", "running", "done", "failed"]
    detail: str | None = Field(None, description="One line on what the agent is doing.")


class TableProps(_Strict):
    columns: list[str]
    rows: list[list[str | float | int | None]]


class KeyValueItem(_Strict):
    label: str
    value: str


class KeyValueProps(_Strict):
    items: list[KeyValueItem]


class CalloutProps(_Strict):
    tone: Literal["info", "success", "warning", "danger"] = "info"
    text: str


class FileProps(_Strict):
    filename: str
    url: str | None = Field(None, description="Download link, once the file exists.")


class OrgNode(_Strict):
    id: str = Field(description="Unique within the block, e.g. 'cloud-architect/finops-analyst'.")
    name: str
    agent: str | None = Field(None, description="Catalog key of the agent.")
    parent: str | None = Field(None, description="Id of the parent node; null for the root.")
    state: Literal["idle", "queued", "running", "done", "failed"] = "idle"
    detail: str | None = Field(None, description="One line: why it was engaged, or what it is doing.")


class OrgProps(_Strict):
    nodes: list[OrgNode]


# -- blocks ------------------------------------------------------------------
class _BlockBase(_Strict):
    title: str | None = None
    agent: str | None = Field(None, description="Catalog key of the agent that owns the block.")


class MarkdownBlock(_BlockBase):
    type: Literal["markdown"] = "markdown"
    props: MarkdownProps


class StatusBlock(_BlockBase):
    type: Literal["status"] = "status"
    props: StatusProps


class TableBlock(_BlockBase):
    type: Literal["table"] = "table"
    props: TableProps


class KeyValueBlock(_BlockBase):
    type: Literal["kv"] = "kv"
    props: KeyValueProps


class CalloutBlock(_BlockBase):
    type: Literal["callout"] = "callout"
    props: CalloutProps


class FileBlock(_BlockBase):
    type: Literal["file"] = "file"
    props: FileProps


class OrgBlock(_BlockBase):
    """A live tree of agents: orchestrator, the leads it engaged, their specialists."""

    type: Literal["org"] = "org"
    props: OrgProps


BlockInput = Annotated[
    MarkdownBlock | StatusBlock | TableBlock | KeyValueBlock | CalloutBlock | FileBlock | OrgBlock,
    Field(discriminator="type"),
]
block_input_adapter: TypeAdapter[BlockInput] = TypeAdapter(BlockInput)

BLOCK_TYPES = ["markdown", "status", "table", "kv", "callout", "file", "org"]


class Block(BaseModel):
    """A block as stored: its validated input plus a server-assigned id."""

    id: str
    type: str
    title: str | None = None
    agent: str | None = None
    props: dict


class Canvas(BaseModel):
    """A canvas as the API returns it. Stored as a doc of kind "canvas" in app.store,
    whose doc holds ``team`` and ``blocks``."""

    id: int
    title: str
    team: str | None = None
    version: int = 1
    blocks: list[Block] = Field(default_factory=list)
    updated: str

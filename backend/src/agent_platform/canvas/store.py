"""Versioned canvas storage with change notification.

Every write takes the version the writer last saw. If the canvas has moved on
since, the write is refused with :class:`VersionConflictError` (HTTP 409) and
nothing changes - the writer must re-read and re-apply. This is what lets an
orchestrator, its specialists and a human in the browser edit the same canvas
without silently overwriting each other.
"""

from __future__ import annotations

import json
import threading
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from .models import Block, BlockInput, Canvas


class CanvasNotFoundError(KeyError):
    pass


class BlockNotFoundError(KeyError):
    pass


class VersionConflictError(Exception):
    def __init__(self, expected: int, actual: int) -> None:
        super().__init__(
            f"canvas is at version {actual}, you wrote against {expected}; "
            "call get_canvas, re-apply your change, and write with the new version"
        )
        self.expected = expected
        self.actual = actual


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def _as_block(block_id: str, block: BlockInput) -> Block:
    data = block.model_dump()
    return Block(id=block_id, **data)


class CanvasStore:
    """In-memory canvases, mirrored to ``<state_dir>/canvases/<id>.json``."""

    def __init__(self, state_dir: Path | None = None) -> None:
        self._dir = state_dir / "canvases" if state_dir else None
        self._canvases: dict[str, Canvas] = {}
        self._cond = threading.Condition()
        self._listeners: list[Callable[[Canvas], None]] = []
        if self._dir and self._dir.is_dir():
            for path in self._dir.glob("*.json"):
                canvas = Canvas.model_validate_json(path.read_text())
                self._canvases[canvas.id] = canvas

    # -- reads -------------------------------------------------------------
    def all(self) -> list[Canvas]:
        with self._cond:
            return sorted(self._canvases.values(), key=lambda c: c.updated_at, reverse=True)

    def get(self, canvas_id: str) -> Canvas:
        with self._cond:
            try:
                return self._canvases[canvas_id].model_copy(deep=True)
            except KeyError:
                raise CanvasNotFoundError(canvas_id) from None

    def wait_for_change(self, canvas_id: str, after_version: int, timeout: float) -> Canvas:
        """Block until the canvas passes ``after_version`` (or timeout); return it."""
        with self._cond:
            self._cond.wait_for(
                lambda: (
                    canvas_id not in self._canvases
                    or self._canvases[canvas_id].version > after_version
                ),
                timeout=timeout,
            )
        return self.get(canvas_id)

    # -- writes ------------------------------------------------------------
    def create(self, title: str, team: str | None = None) -> Canvas:
        canvas = Canvas(id=_new_id("cnv"), title=title, team=team)
        with self._cond:
            self._canvases[canvas.id] = canvas
            self._commit(canvas, bump=False)
        return canvas.model_copy(deep=True)

    def set_title(self, canvas_id: str, title: str) -> Canvas:
        # Like a rename: no version bump, so it never conflicts with block edits.
        with self._cond:
            canvas = self._require(canvas_id)
            canvas.title = title
            self._commit(canvas, bump=False)
            return canvas.model_copy(deep=True)

    def add_block(
        self, canvas_id: str, version: int, block: BlockInput, after: str | None = None
    ) -> tuple[Canvas, str]:
        with self._cond:
            canvas = self._require(canvas_id, version)
            new = _as_block(_new_id("blk"), block)
            index = len(canvas.blocks) if after is None else self._index(canvas, after) + 1
            canvas.blocks.insert(index, new)
            self._commit(canvas)
            return canvas.model_copy(deep=True), new.id

    def update_block(
        self, canvas_id: str, version: int, block_id: str, block: BlockInput
    ) -> Canvas:
        with self._cond:
            canvas = self._require(canvas_id, version)
            i = self._index(canvas, block_id)
            canvas.blocks[i] = _as_block(block_id, block)
            self._commit(canvas)
            return canvas.model_copy(deep=True)

    def move_block(self, canvas_id: str, version: int, block_id: str, index: int) -> Canvas:
        with self._cond:
            canvas = self._require(canvas_id, version)
            block = canvas.blocks.pop(self._index(canvas, block_id))
            canvas.blocks.insert(max(0, min(index, len(canvas.blocks))), block)
            self._commit(canvas)
            return canvas.model_copy(deep=True)

    def delete_block(self, canvas_id: str, version: int, block_id: str) -> Canvas:
        with self._cond:
            canvas = self._require(canvas_id, version)
            canvas.blocks.pop(self._index(canvas, block_id))
            self._commit(canvas)
            return canvas.model_copy(deep=True)

    # -- internals ---------------------------------------------------------
    def _require(self, canvas_id: str, version: int | None = None) -> Canvas:
        canvas = self._canvases.get(canvas_id)
        if canvas is None:
            raise CanvasNotFoundError(canvas_id)
        if version is not None and version != canvas.version:
            raise VersionConflictError(version, canvas.version)
        return canvas

    @staticmethod
    def _index(canvas: Canvas, block_id: str) -> int:
        for i, b in enumerate(canvas.blocks):
            if b.id == block_id:
                return i
        raise BlockNotFoundError(block_id)

    def _commit(self, canvas: Canvas, *, bump: bool = True) -> None:
        if bump:
            canvas.version += 1
        canvas.updated_at = datetime.now(UTC)
        if self._dir:
            self._dir.mkdir(parents=True, exist_ok=True)
            tmp = self._dir / f"{canvas.id}.tmp"
            tmp.write_text(json.dumps(canvas.model_dump(mode="json"), indent=2))
            tmp.replace(self._dir / f"{canvas.id}.json")
        self._cond.notify_all()

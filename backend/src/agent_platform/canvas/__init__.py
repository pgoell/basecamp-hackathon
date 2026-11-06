"""The canvas: shared backend state that agents write and the frontend renders.

Agents never talk to the frontend directly. They change the canvas through
the tools in :mod:`.tools`; every change bumps the canvas version and is
pushed to subscribed browsers, which render each block with the component
registered for its ``type``. Adding a new kind of UI = add a block model here
and a component in ``frontend/src/blocks/``.
"""

from .models import Block, BlockInput, Canvas
from .store import CanvasNotFoundError, CanvasStore, VersionConflictError

__all__ = [
    "Block",
    "BlockInput",
    "Canvas",
    "CanvasNotFoundError",
    "CanvasStore",
    "VersionConflictError",
]

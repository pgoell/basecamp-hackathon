from pathlib import Path

import pytest
from pydantic import ValidationError

from agent_platform.canvas import CanvasStore, VersionConflictError
from agent_platform.canvas.tools import TOOLS, dispatch

MD = {"type": "markdown", "props": {"text": "hi"}}


def test_writes_bump_version_and_stale_writes_are_refused(tmp_path: Path):
    store = CanvasStore(tmp_path)
    c = store.create("t")
    r = dispatch(store, c.id, "add_block", {"version": c.version, "block": MD})
    assert r["version"] == c.version + 1

    with pytest.raises(VersionConflictError):
        dispatch(store, c.id, "add_block", {"version": c.version, "block": MD})
    assert len(store.get(c.id).blocks) == 1  # refused write changed nothing


def test_title_change_does_not_bump_version(tmp_path: Path):
    store = CanvasStore(tmp_path)
    c = store.create("t")
    assert dispatch(store, c.id, "set_title", {"title": "new"})["version"] == c.version


def test_invalid_props_are_rejected(tmp_path: Path):
    store = CanvasStore(tmp_path)
    c = store.create("t")
    bad = {"type": "status", "props": {"state": "sleeping"}}
    with pytest.raises(ValidationError):
        dispatch(store, c.id, "add_block", {"version": c.version, "block": bad})


def test_canvases_persist(tmp_path: Path):
    c = CanvasStore(tmp_path).create("kept")
    assert CanvasStore(tmp_path).get(c.id).title == "kept"


def test_tool_definitions_are_claude_shaped():
    names = {t["name"] for t in TOOLS}
    assert {"get_canvas", "add_block", "update_block", "move_block", "delete_block"} <= names
    assert all({"name", "description", "input_schema"} <= set(t) for t in TOOLS)

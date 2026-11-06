import pytest
from fastapi import HTTPException

from app.canvas import store as canvases
from app.canvas.tools import TOOLS, dispatch

MD = {"type": "markdown", "props": {"text": "hi"}}


def test_writes_bump_version_and_stale_writes_are_refused():
    c = canvases.create("t")
    r = dispatch(c.id, "add_block", {"version": c.version, "block": MD})
    assert r["version"] == c.version + 1

    with pytest.raises(HTTPException) as e:
        dispatch(c.id, "add_block", {"version": c.version, "block": MD})
    assert e.value.status_code == 409
    assert len(canvases.get(c.id).blocks) == 1  # refused write changed nothing


def test_title_change_does_not_bump_version():
    c = canvases.create("t")
    assert dispatch(c.id, "set_title", {"title": "new"})["version"] == c.version
    assert canvases.get(c.id).title == "new"


def test_invalid_props_are_rejected():
    c = canvases.create("t")
    bad = {"type": "status", "props": {"state": "sleeping"}}
    with pytest.raises(HTTPException) as e:
        dispatch(c.id, "add_block", {"version": c.version, "block": bad})
    assert e.value.status_code == 422


def test_move_and_delete_blocks():
    c = canvases.create("t")
    a = dispatch(c.id, "add_block", {"version": 1, "block": MD})["block_id"]
    b = dispatch(c.id, "add_block", {"version": 2, "block": MD})["block_id"]
    dispatch(c.id, "move_block", {"version": 3, "block_id": b, "index": 0})
    assert [x.id for x in canvases.get(c.id).blocks] == [b, a]
    dispatch(c.id, "delete_block", {"version": 4, "block_id": b})
    assert [x.id for x in canvases.get(c.id).blocks] == [a]


def test_tool_definitions_are_claude_shaped():
    names = {t["name"] for t in TOOLS}
    assert {"get_canvas", "add_block", "update_block", "move_block", "delete_block"} <= names
    assert all({"name", "description", "input_schema"} <= set(t) for t in TOOLS)

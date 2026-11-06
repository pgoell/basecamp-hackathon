import pytest
from fastapi import HTTPException

from app import store


def test_doc_write_needs_the_current_version():
    d = store.create("slides", "Deck", {"slides": []})
    assert store.write(d["id"], 1, doc={"slides": [1]})["version"] == 2
    with pytest.raises(store.VersionConflict) as e:
        store.write(d["id"], 1, doc={"slides": [2]})
    assert (e.value.status_code, e.value.expected, e.value.actual) == (409, 1, 2)
    assert store.get(d["id"])["doc"] == {"slides": [1]}


def test_title_alone_keeps_the_version_and_empty_doc_is_a_doc():
    d = store.create("canvas", "a", {"blocks": [1]})
    assert store.write(d["id"], None, title="b")["version"] == 1
    out = store.write(d["id"], 1, doc={})
    assert (out["title"], out["version"], out["doc"]) == ("b", 2, {})


def test_kinds_are_kept_apart():
    d = store.create("canvas", "c", {})
    with pytest.raises(HTTPException) as e:
        store.get(d["id"], "slides")
    assert e.value.status_code == 404
    assert store.list_all("slides") == []
    assert "doc" not in store.list_all("canvas")[0]
    assert store.list_all("canvas", with_doc=True)[0]["doc"] == {}


def test_one_connection_for_several_calls():
    con = store.connect()
    d = store.create("canvas", "c", {}, con=con)
    assert store.get(d["id"], con=con)["title"] == "c"
    con.close()

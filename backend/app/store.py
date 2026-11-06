"""Versioned JSON docs in SQLite, shared by the canvas and the slides.

A doc change names the version it was based on. If the doc has moved on since,
the write is refused with 409 and nothing changes: the writer reads again and
re-applies its change. A title change alone never moves the version. Every
write wakes `wait`, which the SSE streams sleep on.

Pass `con` to run several calls on one connection; leave it out to open one.
"""

import json
import os
import sqlite3
import threading
from pathlib import Path

from fastapi import HTTPException

DATA = Path(os.environ.get("DATA_DIR", Path(__file__).resolve().parents[1] / "data"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS docs (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL,
    title TEXT NOT NULL,
    doc TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    updated TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""
COLUMNS = "id, kind, title, doc, version, updated"

_changed = threading.Condition()
_tick = 0


class VersionConflict(HTTPException):
    def __init__(self, expected: int, actual: int) -> None:
        message = (
            f"The doc is at version {actual}, you wrote against {expected}. "
            "Read it again, re-apply your change and write with the new version."
        )
        super().__init__(409, {"message": message, "expected": expected, "actual": actual})
        self.expected = expected
        self.actual = actual


def connect() -> sqlite3.Connection:
    """A connection in autocommit mode, rows as dicts by column. FastAPI may open it in one
    thread and use it in another, never in two at once."""
    DATA.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(
        DATA / "basecamp.db", isolation_level=None, timeout=10, check_same_thread=False
    )
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA journal_mode = WAL")
    con.executescript(SCHEMA)
    return con


def _with(con, fn):
    if con is not None:
        return fn(con)
    own = connect()
    try:
        return fn(own)
    finally:
        own.close()


def _public(row: sqlite3.Row) -> dict:
    out = dict(row)
    if "doc" in out:
        out["doc"] = json.loads(out["doc"])
    return out


def _notify() -> None:
    global _tick
    with _changed:
        _tick += 1
        _changed.notify_all()


def tick() -> int:
    return _tick


def wait(seen: int, timeout: float) -> int:
    """Sleep until a write after tick `seen`, or `timeout` seconds. Returns the new tick."""
    with _changed:
        _changed.wait_for(lambda: _tick != seen, timeout)
        return _tick


def create(kind: str, title: str, doc: dict, con: sqlite3.Connection | None = None) -> dict:
    def run(con):
        row = con.execute(
            f"INSERT INTO docs (kind, title, doc) VALUES (?, ?, ?) RETURNING {COLUMNS}",
            (kind, title, json.dumps(doc)),
        ).fetchone()
        return _public(row)

    out = _with(con, run)
    _notify()
    return out


def get(doc_id: int, kind: str | None = None, con: sqlite3.Connection | None = None) -> dict:
    row = _with(
        con, lambda c: c.execute(f"SELECT {COLUMNS} FROM docs WHERE id = ?", (doc_id,)).fetchone()
    )
    if row is None or (kind and row["kind"] != kind):
        raise HTTPException(404, f"No {kind or 'doc'} with id {doc_id}.")
    return _public(row)


def list_all(kind: str, with_doc: bool = False, con: sqlite3.Connection | None = None) -> list:
    columns = COLUMNS if with_doc else COLUMNS.replace(" doc,", "")
    rows = _with(
        con,
        lambda c: c.execute(
            f"SELECT {columns} FROM docs WHERE kind = ? ORDER BY updated DESC, id DESC", (kind,)
        ).fetchall(),
    )
    return [_public(r) for r in rows]


def write(
    doc_id: int,
    version: int | None,
    title: str | None = None,
    doc: dict | None = None,
    con: sqlite3.Connection | None = None,
) -> dict:
    """Stores a new title and/or doc. A doc moves the version on, and only from `version`."""

    def run(con):
        row = con.execute(
            "UPDATE docs SET title = COALESCE(?1, title), doc = COALESCE(?2, doc),"
            " version = version + (?2 IS NOT NULL), updated = CURRENT_TIMESTAMP"
            f" WHERE id = ?3 AND (?2 IS NULL OR version = ?4) RETURNING {COLUMNS}",
            (title, None if doc is None else json.dumps(doc), doc_id, version),
        ).fetchone()
        if row is None:
            raise VersionConflict(version, get(doc_id, con=con)["version"])
        return _public(row)

    out = _with(con, run)
    _notify()
    return out


def delete(doc_id: int, con: sqlite3.Connection | None = None) -> None:
    _with(con, lambda c: c.execute("DELETE FROM docs WHERE id = ?", (doc_id,)))
    _notify()

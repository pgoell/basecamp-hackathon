"""Presentations: a title and the doc, shared by everyone. Ported from blattwerk's sheets.py."""

import json
import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator

from app.slides import db, ops
from app.slides.schema import problems

router = APIRouter(prefix="/api/slides")
Con = Annotated[sqlite3.Connection, Depends(db.con)]
Title = Annotated[str, Field(min_length=1, max_length=120)]
COLUMNS = "id, title, doc, version, updated"


class New(BaseModel):
    title: Title


class Change(BaseModel):
    title: Title | None = None
    doc: dict | None = None
    # The version the doc was based on. A rename brings neither.
    version: int | None = None

    @model_validator(mode="after")
    def doc_has_version(self) -> "Change":
        if self.doc is not None and self.version is None:
            raise ValueError("a doc needs the version it was based on")
        return self


def public(row: sqlite3.Row | None) -> dict:
    if not row:
        raise HTTPException(404)
    return {**row, "doc": json.loads(row["doc"])}


def find(con: sqlite3.Connection, pid: int) -> dict:
    return public(con.execute(f"SELECT {COLUMNS} FROM presentations WHERE id = ?", (pid,)).fetchone())


def refuse_faults(doc: dict) -> None:
    found = problems(doc)
    if found:
        raise HTTPException(422, detail={"problems": found})


def write(con: sqlite3.Connection, pid: int, version: int, title: str | None, doc: dict | None) -> dict:
    """Stores a new title and/or doc. A doc moves the version on, and only from `version`: a doc
    based on an older one answers 409."""
    if doc is not None:
        refuse_faults(doc)
    row = con.execute(
        "UPDATE presentations SET title = coalesce(?1, title), doc = coalesce(?2, doc),"
        " version = version + (?2 IS NOT NULL), updated = CURRENT_TIMESTAMP"
        " WHERE id = ?3 AND (?2 IS NULL OR version = ?4)"
        f" RETURNING {COLUMNS}",
        (title, doc and json.dumps(doc), pid, version),
    ).fetchone()
    if not row:
        find(con, pid)
        raise HTTPException(409)
    return public(row)


@router.get("/presentations")
def list_all(con: Con) -> list[dict]:
    # The list page draws each first slide, so the doc comes along.
    rows = con.execute(f"SELECT {COLUMNS} FROM presentations ORDER BY updated DESC, id DESC")
    return [public(row) for row in rows]


@router.post("/presentations")
def create(body: New, con: Con) -> dict:
    doc = {"slides": []}
    ops.add_slide(doc, "title", title=body.title)
    return public(
        con.execute(
            f"INSERT INTO presentations (title, doc) VALUES (?, ?) RETURNING {COLUMNS}",
            (body.title, json.dumps(doc)),
        ).fetchone()
    )


@router.get("/presentations/{pid}")
def get(pid: int, con: Con) -> dict:
    return find(con, pid)


@router.patch("/presentations/{pid}")
def save(pid: int, body: Change, con: Con) -> dict:
    return write(con, pid, body.version, body.title, body.doc)


@router.delete("/presentations/{pid}")
def delete(pid: int, con: Con) -> dict:
    if not con.execute("DELETE FROM presentations WHERE id = ?", (pid,)).rowcount:
        raise HTTPException(404)
    return {}

"""Presentations: a title and the doc, shared by everyone. Ported from blattwerk's sheets.py."""

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator

from app import store
from app.slides import db, ops
from app.slides.schema import problems

router = APIRouter(prefix="/api/slides")
Con = Annotated[sqlite3.Connection, Depends(db.con)]
Title = Annotated[str, Field(min_length=1, max_length=120)]
KIND = "slides"


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


def find(con: sqlite3.Connection, pid: int) -> dict:
    return store.get(pid, KIND, con=con)


def refuse_faults(doc: dict) -> None:
    found = problems(doc)
    if found:
        raise HTTPException(422, detail={"problems": found})


def write(con: sqlite3.Connection, pid: int, version: int | None, title: str | None, doc: dict | None) -> dict:
    """Stores a new title and/or doc. A doc moves the version on, and only from `version`: a doc
    based on an older one answers 409."""
    find(con, pid)
    if doc is not None:
        refuse_faults(doc)
    return store.write(pid, version, title, doc, con=con)


@router.get("/presentations")
def list_all(con: Con) -> list[dict]:
    # The list page draws each first slide, so the doc comes along.
    return store.list_all(KIND, with_doc=True, con=con)


@router.post("/presentations")
def create(body: New, con: Con) -> dict:
    doc = {"slides": []}
    ops.add_slide(doc, "title", title=body.title)
    return store.create(KIND, body.title, doc, con=con)


@router.get("/presentations/{pid}")
def get(pid: int, con: Con) -> dict:
    return find(con, pid)


@router.patch("/presentations/{pid}")
def save(pid: int, body: Change, con: Con) -> dict:
    return write(con, pid, body.version, body.title, body.doc)


@router.delete("/presentations/{pid}")
def delete(pid: int, con: Con) -> dict:
    find(con, pid)
    store.delete(pid, con=con)
    return {}

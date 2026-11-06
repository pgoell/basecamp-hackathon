"""SQLite: presentations, their chats, and each chat's messages."""

import os
import sqlite3
from pathlib import Path

DATA = Path(os.environ.get("DATA_DIR", Path(__file__).resolve().parents[2] / "data"))
UPLOADS = DATA / "uploads"

SCHEMA = """
CREATE TABLE IF NOT EXISTS presentations (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    doc TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    updated TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS chats (
    id INTEGER PRIMARY KEY,
    presentation_id INTEGER NOT NULL REFERENCES presentations(id) ON DELETE CASCADE,
    title TEXT NOT NULL DEFAULT 'New chat',
    created TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY,
    chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


def connect() -> sqlite3.Connection:
    """A connection in autocommit mode, rows as dicts by column. FastAPI may open it in one
    thread and use it in another, never in two at once."""
    con = sqlite3.connect(DATA / "slides.db", isolation_level=None, timeout=10, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def setup() -> None:
    UPLOADS.mkdir(parents=True, exist_ok=True)
    con = connect()
    con.execute("PRAGMA journal_mode = WAL")
    con.executescript(SCHEMA)
    con.close()


def con():
    """FastAPI dependency: one connection per request."""
    c = connect()
    try:
        yield c
    finally:
        c.close()


setup()

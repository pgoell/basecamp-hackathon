"""SQLite: the slides' chats and messages, beside the presentations in the shared store
(app/store.py, table docs, kind 'slides')."""

import sqlite3

from app import store

UPLOADS = store.DATA / "uploads"

SCHEMA = """
CREATE TABLE IF NOT EXISTS chats (
    id INTEGER PRIMARY KEY,
    presentation_id INTEGER NOT NULL REFERENCES docs(id) ON DELETE CASCADE,
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
    """A connection to the shared store (autocommit, rows by column, foreign keys on)."""
    return store.connect()


def migrate(con: sqlite3.Connection) -> None:
    """Moves the old slides.db into the store once, with new ids, then renames it so it is not
    read again."""
    old = store.DATA / "slides.db"
    if not old.exists():
        return
    src = sqlite3.connect(old)
    src.row_factory = sqlite3.Row
    con.execute("BEGIN")
    try:
        ids = {}
        for p in src.execute("SELECT * FROM presentations ORDER BY id"):
            ids[p["id"]] = con.execute(
                "INSERT INTO docs (kind, title, doc, version, updated) VALUES ('slides', ?, ?, ?, ?) RETURNING id",
                (p["title"], p["doc"], p["version"], p["updated"]),
            ).fetchone()[0]
        chats = {}
        for c in src.execute("SELECT * FROM chats ORDER BY id"):
            if c["presentation_id"] in ids:
                chats[c["id"]] = con.execute(
                    "INSERT INTO chats (presentation_id, title, created) VALUES (?, ?, ?) RETURNING id",
                    (ids[c["presentation_id"]], c["title"], c["created"]),
                ).fetchone()[0]
        for m in src.execute("SELECT * FROM messages ORDER BY id"):
            if m["chat_id"] in chats:
                con.execute(
                    "INSERT INTO messages (chat_id, role, content, created) VALUES (?, ?, ?, ?)",
                    (chats[m["chat_id"]], m["role"], m["content"], m["created"]),
                )
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    finally:
        src.close()
    old.rename(old.with_name("slides.db.migrated"))


def setup() -> None:
    UPLOADS.mkdir(parents=True, exist_ok=True)
    con = connect()
    con.executescript(SCHEMA)
    migrate(con)
    con.close()


def con():
    """FastAPI dependency: one connection per request."""
    c = connect()
    try:
        yield c
    finally:
        c.close()


setup()

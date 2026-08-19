"""SQLite connection, pragmas, and numbered migrations via user_version."""

from __future__ import annotations

import sqlite3
from pathlib import Path

_MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"

# version -> filename (sorted by version number)
_MIGRATION_FILES: dict[int, str] = {
    1: "001_initial.sql",
    2: "002_enrich_queue.sql",
}


def connect(path: str | Path, *, read_only: bool = False) -> sqlite3.Connection:
    db_path = Path(path)
    if read_only:
        uri = f"file:{db_path.resolve()}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
    else:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    _apply_pragmas(conn, read_only=read_only)
    if not read_only:
        migrate(conn)
    return conn


def _apply_pragmas(conn: sqlite3.Connection, *, read_only: bool) -> None:
    if not read_only:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")


def migrate(conn: sqlite3.Connection) -> int:
    """Apply pending SQL migrations. Returns final user_version."""
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    for version, filename in sorted(_MIGRATION_FILES.items()):
        if version <= current:
            continue
        sql = (_MIGRATIONS_DIR / filename).read_text(encoding="utf-8")
        conn.executescript(sql)
        conn.execute(f"PRAGMA user_version = {version}")
        conn.commit()
    return int(conn.execute("PRAGMA user_version").fetchone()[0])


def user_version(conn: sqlite3.Connection) -> int:
    return int(conn.execute("PRAGMA user_version").fetchone()[0])

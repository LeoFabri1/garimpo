"""Repository helpers for raw_messages and sources."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime


def ensure_source(
    conn: sqlite3.Connection,
    *,
    tg_id: int,
    username: str | None = None,
    title: str | None = None,
    parser: str = "generic",
) -> int:
    row = conn.execute("SELECT id FROM sources WHERE tg_id = ?", (tg_id,)).fetchone()
    if row:
        return int(row["id"])
    now = _iso(datetime.now(UTC).replace(tzinfo=None))
    cur = conn.execute(
        """
        INSERT INTO sources (tg_id, username, title, parser, enabled, added_at)
        VALUES (?, ?, ?, ?, 1, ?)
        """,
        (tg_id, username, title, parser, now),
    )
    conn.commit()
    return int(cur.lastrowid)


def get_raw_by_tg(
    conn: sqlite3.Connection, source_id: int, tg_msg_id: int
) -> tuple[int, str] | None:
    row = conn.execute(
        """
        SELECT id, status FROM raw_messages
        WHERE source_id = ? AND tg_msg_id = ?
        """,
        (source_id, tg_msg_id),
    ).fetchone()
    if row is None:
        return None
    return int(row["id"]), str(row["status"])


def insert_raw_message(
    conn: sqlite3.Connection,
    *,
    source_id: int,
    tg_msg_id: int,
    text: str | None,
    text_hash: str,
    has_media: bool,
    received_at: datetime,
    status: str,
    parser_used: str | None = None,
    fail_reason: str | None = None,
) -> int:
    """Insert raw message. On (source_id, tg_msg_id) conflict, return existing id."""
    existing = get_raw_by_tg(conn, source_id, tg_msg_id)
    if existing is not None:
        return existing[0]

    try:
        cur = conn.execute(
            """
            INSERT INTO raw_messages (
                source_id, tg_msg_id, text, text_hash, has_media,
                received_at, status, parser_used, fail_reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_id,
                tg_msg_id,
                text,
                text_hash,
                1 if has_media else 0,
                _iso(received_at),
                status,
                parser_used,
                fail_reason,
            ),
        )
        conn.commit()
        return int(cur.lastrowid)
    except sqlite3.IntegrityError:
        again = get_raw_by_tg(conn, source_id, tg_msg_id)
        if again is None:
            raise
        return again[0]


def update_raw_status(
    conn: sqlite3.Connection,
    raw_id: int,
    *,
    status: str,
    parser_used: str | None = None,
    fail_reason: str | None = None,
) -> None:
    conn.execute(
        """
        UPDATE raw_messages
        SET status = ?, parser_used = COALESCE(?, parser_used),
            fail_reason = COALESCE(?, fail_reason)
        WHERE id = ?
        """,
        (status, parser_used, fail_reason, raw_id),
    )
    conn.commit()


def recent_hash_exists(
    conn: sqlite3.Connection,
    text_hash: str,
    *,
    within_minutes: int = 10,
    now: datetime | None = None,
) -> bool:
    now = now or datetime.now(UTC).replace(tzinfo=None)
    # Compare ISO strings with a simple window using datetime arithmetic in Python
    row = conn.execute(
        """
        SELECT id, received_at FROM raw_messages
        WHERE text_hash = ?
        ORDER BY id DESC LIMIT 5
        """,
        (text_hash,),
    ).fetchall()
    for r in row:
        try:
            received = datetime.fromisoformat(r["received_at"])
        except ValueError:
            continue
        delta = (now - received).total_seconds()
        if 0 <= delta <= within_minutes * 60:
            return True
    return False


def count_by_status(conn: sqlite3.Connection) -> dict[str, int]:
    rows = conn.execute(
        "SELECT status, COUNT(*) AS n FROM raw_messages GROUP BY status"
    ).fetchall()
    return {str(r["status"]): int(r["n"]) for r in rows}


def _iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat()

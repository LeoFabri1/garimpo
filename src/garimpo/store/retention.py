"""Retention purge for noisy raw_messages (DESIGN §6.3)."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta


def purge_raw_noise(
    conn: sqlite3.Connection,
    *,
    retention_days: int = 30,
    now: datetime | None = None,
) -> int:
    """Delete triaged_out / duplicate raw rows older than retention_days."""
    now = now or datetime.now(UTC).replace(tzinfo=None)
    cutoff = (now - timedelta(days=retention_days)).isoformat()
    cur = conn.execute(
        """
        DELETE FROM raw_messages
        WHERE status IN ('triaged_out', 'duplicate')
          AND received_at < ?
        """,
        (cutoff,),
    )
    conn.commit()
    return int(cur.rowcount)

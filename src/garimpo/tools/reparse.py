"""Reparse raw messages with current parsers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from garimpo.models.raw import RawMessage
from garimpo.pipeline import Pipeline
from garimpo.settings import Settings
from garimpo.store.db import connect


def reparse(
    settings: Settings,
    *,
    status: str = "parse_failed",
    since_days: int = 30,
    dry_run: bool = True,
) -> int:
    conn = connect(settings.storage.path)
    since = (
        datetime.now(UTC).replace(tzinfo=None) - timedelta(days=since_days)
    ).isoformat()
    rows = conn.execute(
        """
        SELECT id, source_id, tg_msg_id, text, has_media, received_at
        FROM raw_messages
        WHERE status = ? AND received_at >= ?
        ORDER BY id ASC
        """,
        (status, since),
    ).fetchall()
    conn.close()

    pipe = Pipeline(settings, dry_run=dry_run)
    n = 0
    try:
        for r in rows:
            # Allow re-insert by using a synthetic high tg_msg_id offset for dry tooling
            # Prefer updating: delete unique conflict by processing only parse path.
            # Simplest: feed with unique tg_msg_id = id + 10_000_000
            msg = RawMessage(
                source_id=int(r["source_id"]),
                tg_msg_id=10_000_000 + int(r["id"]),
                text=r["text"],
                has_media=bool(r["has_media"]),
                received_at=datetime.fromisoformat(r["received_at"]),
            )
            result = pipe.process(msg)
            if result.status in {"parsed", "alerted"}:
                n += 1
    finally:
        pipe.close()
    return n

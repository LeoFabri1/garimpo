"""Gap recovery after reconnect / --once mode."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta

from garimpo.ingest.base import MTProtoClient, SourceRef
from garimpo.models.raw import RawMessage
from garimpo.pipeline import Pipeline

ALERT_MAX_AGE = timedelta(minutes=15)
DEFAULT_FETCH_LIMIT = 200


def get_last_msg_id(conn: sqlite3.Connection, tg_id: int) -> int:
    row = conn.execute(
        "SELECT last_msg_id FROM sources WHERE tg_id = ?", (tg_id,)
    ).fetchone()
    if row is None or row["last_msg_id"] is None:
        return 0
    return int(row["last_msg_id"])


def set_last_msg_id(conn: sqlite3.Connection, tg_id: int, msg_id: int) -> None:
    conn.execute(
        """
        UPDATE sources SET last_msg_id = ?, last_seen_at = ?
        WHERE tg_id = ?
        """,
        (msg_id, datetime.now(UTC).replace(tzinfo=None).isoformat(), tg_id),
    )
    conn.commit()


async def recover_source(
    client: MTProtoClient,
    pipeline: Pipeline,
    source: SourceRef,
    *,
    now: datetime | None = None,
    limit: int = DEFAULT_FETCH_LIMIT,
    alert: bool = True,
) -> int:
    """Fetch messages since last_msg_id and process them.

    Offers older than 15 minutes are stored but do not generate alerts
    when ``alert`` is True.
    """
    now = now or datetime.now(UTC)
    resolved = await client.resolve_source(source)
    if resolved.tg_id is None:
        return 0

    # Ensure DB source row uses real tg_id
    from garimpo.store.repo import messages as messages_repo

    messages_repo.ensure_source(
        pipeline.conn,
        tg_id=resolved.tg_id,
        username=resolved.username,
        parser=resolved.parser,
    )

    min_id = get_last_msg_id(pipeline.conn, resolved.tg_id)
    messages = await client.fetch_since(resolved, min_id=min_id, limit=limit)
    count = 0
    max_id = min_id
    for msg in messages:
        max_id = max(max_id, msg.tg_msg_id)
        suppress = False
        if alert:
            age = _age(now, msg.received_at)
            if age > ALERT_MAX_AGE:
                suppress = True
        if suppress:
            _process_without_alert(pipeline, msg)
        else:
            pipeline.process(msg)
        count += 1

    if max_id > min_id:
        set_last_msg_id(pipeline.conn, resolved.tg_id, max_id)
    return count


def _age(now: datetime, received: datetime) -> timedelta:
    if received.tzinfo is None:
        received = received.replace(tzinfo=UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    return now - received


def _process_without_alert(pipeline: Pipeline, msg: RawMessage) -> None:
    """Process into DB/history but skip channel send for stale recoveries."""
    prev = pipeline.dry_run
    # Force dry_run path that still records alerts as dry_run — better: temp flag
    # Use a narrow approach: process normally but swap channel to no-op.
    from garimpo.alert.channels.console import ConsoleChannel

    class _NullChannel(ConsoleChannel):
        name = "null"

        def send(self, scored: object, *, silent: bool = False) -> None:  # type: ignore[override]
            return

    old_channel = pipeline.channel
    pipeline.channel = _NullChannel()  # type: ignore[assignment]
    pipeline.dry_run = True
    try:
        pipeline.process(msg)
    finally:
        pipeline.channel = old_channel
        pipeline.dry_run = prev

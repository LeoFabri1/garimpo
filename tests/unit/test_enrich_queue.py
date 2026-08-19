"""Enrich queue enqueue smoke."""

from datetime import datetime
from pathlib import Path

from garimpo.enrich.queue import enqueue, list_ready
from garimpo.store.db import connect
from garimpo.store.repo import messages as messages_repo


def test_enqueue_and_list(tmp_path: Path) -> None:
    conn = connect(tmp_path / "e.db")
    sid = messages_repo.ensure_source(conn, tg_id=1)
    rid = messages_repo.insert_raw_message(
        conn,
        source_id=sid,
        tg_msg_id=1,
        text="noise",
        text_hash="x",
        has_media=False,
        received_at=datetime(2026, 1, 1),
        status="parse_failed",
    )
    enqueue(conn, rid)
    ready = list_ready(conn)
    assert len(ready) == 1
    assert int(ready[0]["raw_id"]) == rid

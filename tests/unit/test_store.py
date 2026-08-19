"""SQLite migration and repo smoke tests."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from garimpo.store.db import connect, user_version
from garimpo.store.repo import history as history_repo
from garimpo.store.repo import messages as messages_repo


def test_migrate_sets_user_version(tmp_path: Path) -> None:
    db = tmp_path / "t.db"
    conn = connect(db)
    assert user_version(conn) == 1
    # idempotent
    assert connect(db).execute("PRAGMA user_version").fetchone()[0] == 1
    conn.close()


def test_insert_raw_and_history(tmp_path: Path) -> None:
    conn = connect(tmp_path / "t.db")
    sid = messages_repo.ensure_source(conn, tg_id=-1001, username="demo")
    rid = messages_repo.insert_raw_message(
        conn,
        source_id=sid,
        tg_msg_id=10,
        text="hello",
        text_hash="abc",
        has_media=False,
        received_at=datetime(2026, 1, 1),
        status="parsed",
    )
    assert rid > 0
    hid = history_repo.insert_history(
        conn,
        model_key="rtx_5070_ti",
        price=5799.0,
        observed_at=datetime(2026, 1, 1),
        origin="backfill",
        store="kabum",
    )
    assert hid is not None
    assert history_repo.count_history(conn) == 1
    conn.close()

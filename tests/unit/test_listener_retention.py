"""The 24/7 daemon must bound raw_messages growth (no network)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from garimpo.ingest.base import SourceRef
from garimpo.ingest.clients.fake_client import FakeMTProtoClient
from garimpo.ingest.listener import _retention_loop, run_once
from garimpo.models.raw import RawMessage
from garimpo.pipeline import Pipeline
from garimpo.settings import load_settings
from garimpo.store.repo import messages as messages_repo


def _pipeline(tmp_path: Path, *, retention_days: int = 7) -> Pipeline:
    settings = load_settings(Path("config/quickstart.yaml"))
    settings.storage.path = str(tmp_path / "g.db")
    settings.alerts.channel = "console"
    settings.storage.retention_raw_days = retention_days
    return Pipeline(settings, dry_run=True)


def _seed_old_noise(pipe: Pipeline, *, days_old: int = 30) -> None:
    old = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=days_old)
    source_id = messages_repo.ensure_source(
        pipe.conn, tg_id=7, username="old", parser="generic"
    )
    for i, status in enumerate(["triaged_out", "duplicate"]):
        messages_repo.insert_raw_message(
            pipe.conn,
            source_id=source_id,
            tg_msg_id=5000 + i,
            text="ruido antigo",
            text_hash=f"old{i}",
            has_media=False,
            received_at=old,
            status=status,
        )


@pytest.mark.asyncio
async def test_run_once_purges_expired_noise(tmp_path: Path) -> None:
    pipe = _pipeline(tmp_path)
    client = FakeMTProtoClient()
    src = SourceRef(username="promobit_hardware", tg_id=42, parser="generic")
    now = datetime.now(UTC)
    client.seed(
        src,
        [
            RawMessage(
                42,
                10,
                "RTX 5070 Ti ASUS — R$ 5.799 no PIX Kabum",
                False,
                now - timedelta(minutes=2),
                source_username="promobit_hardware",
            ),
        ],
    )
    try:
        _seed_old_noise(pipe)
        assert messages_repo.count_by_status(pipe.conn).get("triaged_out") == 1

        processed = await run_once(client, pipe, [src])

        assert processed == 1
        remaining = messages_repo.count_by_status(pipe.conn)
        assert "triaged_out" not in remaining
        assert "duplicate" not in remaining
    finally:
        pipe.close()


@pytest.mark.asyncio
async def test_retention_loop_purges_then_honors_stop(tmp_path: Path) -> None:
    pipe = _pipeline(tmp_path)
    try:
        _seed_old_noise(pipe)
        stop = asyncio.Event()
        # A long interval proves the first purge happens before any sleep.
        task = asyncio.create_task(_retention_loop(pipe, stop, interval_hours=24))
        await asyncio.sleep(0)
        stop.set()
        await asyncio.wait_for(task, timeout=2)

        assert "triaged_out" not in messages_repo.count_by_status(pipe.conn)
    finally:
        pipe.close()

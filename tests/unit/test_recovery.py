"""Gap recovery with FakeMTProtoClient (no network)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from garimpo.ingest.base import SourceRef
from garimpo.ingest.clients.fake_client import FakeMTProtoClient
from garimpo.ingest.recovery import ALERT_MAX_AGE, recover_source
from garimpo.models.raw import RawMessage
from garimpo.pipeline import Pipeline
from garimpo.settings import load_settings


@pytest.mark.asyncio
async def test_recovery_processes_and_advances_cursor(tmp_path: Path) -> None:
    settings = load_settings(Path("config/quickstart.yaml"))
    settings.storage.path = str(tmp_path / "g.db")
    settings.alerts.channel = "console"

    pipe = Pipeline(settings, dry_run=True)
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
        await client.start()
        n = await recover_source(client, pipe, src, now=now, alert=True)
        assert n == 1
        # second pass: nothing new
        n2 = await recover_source(client, pipe, src, now=now, alert=True)
        assert n2 == 0
    finally:
        await client.stop()
        pipe.close()


@pytest.mark.asyncio
async def test_stale_messages_do_not_crash(tmp_path: Path) -> None:
    settings = load_settings(Path("config/quickstart.yaml"))
    settings.storage.path = str(tmp_path / "g.db")
    pipe = Pipeline(settings, dry_run=True)
    client = FakeMTProtoClient()
    src = SourceRef(username="promobit_hardware", tg_id=99)
    now = datetime.now(UTC)
    stale = now - ALERT_MAX_AGE - timedelta(minutes=5)
    client.seed(
        src,
        [
            RawMessage(
                99,
                1,
                "RTX 5070 Ti — R$ 5.500 no PIX Kabum",
                False,
                stale,
                source_username="promobit_hardware",
            ),
        ],
    )
    try:
        await client.start()
        n = await recover_source(client, pipe, src, now=now, alert=True)
        assert n == 1
    finally:
        await client.stop()
        pipe.close()

"""Backlog recovery must not alert on stale offers.

The first `run --once` fetches up to 200 backlog messages. Alerting on all of
them would burst into the user's Telegram for deals that expired hours ago.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from garimpo.ingest.base import SourceRef
from garimpo.ingest.clients.fake_client import FakeMTProtoClient
from garimpo.ingest.recovery import ALERT_MAX_AGE, recover_source
from garimpo.models.alert import ScoredOffer
from garimpo.models.raw import RawMessage
from garimpo.pipeline import Pipeline
from garimpo.settings import load_settings

_DEAL = "RTX 5070 Ti ASUS — R$ 5.799 no PIX Kabum"


class RecordingChannel:
    """Stands in for Saved Messages so we can count real sends."""

    name = "recording"

    def __init__(self) -> None:
        self.sent: list[ScoredOffer] = []

    def send(self, scored: ScoredOffer, *, silent: bool = False) -> None:
        self.sent.append(scored)


def _pipeline(tmp_path: Path, channel: RecordingChannel) -> Pipeline:
    settings = load_settings(Path("config/quickstart.yaml"))
    settings.storage.path = str(tmp_path / "g.db")
    # dry_run=False so a real send would actually reach the channel
    return Pipeline(settings, channel=channel, dry_run=False)


async def _recover_one(
    pipe: Pipeline, *, age: timedelta, tg_msg_id: int, tg_id: int
) -> int:
    client = FakeMTProtoClient()
    src = SourceRef(username="promobit_hardware", tg_id=tg_id, parser="generic")
    now = datetime.now(UTC)
    client.seed(
        src,
        [
            RawMessage(
                tg_id,
                tg_msg_id,
                _DEAL,
                False,
                now - age,
                source_username="promobit_hardware",
            )
        ],
    )
    await client.start()
    try:
        return await recover_source(client, pipe, src, now=now, alert=True)
    finally:
        await client.stop()


@pytest.mark.asyncio
async def test_stale_backlog_is_stored_but_never_sent(tmp_path: Path) -> None:
    channel = RecordingChannel()
    pipe = _pipeline(tmp_path, channel)
    try:
        n = await _recover_one(
            pipe, age=ALERT_MAX_AGE + timedelta(hours=3), tg_msg_id=10, tg_id=42
        )
        assert n == 1, "the message must still be ingested"
        assert channel.sent == [], (
            f"stale offer was sent to the channel: {[s.reason for s in channel.sent]}"
        )

        # It has to reach price_history, otherwise the baseline never builds.
        rows = pipe.conn.execute("SELECT COUNT(*) AS n FROM price_history").fetchone()
        assert rows["n"] == 1
    finally:
        pipe.close()


@pytest.mark.asyncio
async def test_fresh_offer_does_reach_the_channel(tmp_path: Path) -> None:
    channel = RecordingChannel()
    pipe = _pipeline(tmp_path, channel)
    try:
        await _recover_one(pipe, age=timedelta(minutes=2), tg_msg_id=11, tg_id=43)
        assert len(channel.sent) == 1, "a fresh offer must still alert"
    finally:
        pipe.close()


@pytest.mark.asyncio
async def test_stale_offer_is_recorded_as_suppressed(tmp_path: Path) -> None:
    channel = RecordingChannel()
    pipe = _pipeline(tmp_path, channel)
    try:
        await _recover_one(
            pipe, age=ALERT_MAX_AGE + timedelta(hours=1), tg_msg_id=12, tg_id=44
        )
        row = pipe.conn.execute(
            "SELECT status, suppressed_by FROM alerts ORDER BY id DESC LIMIT 1"
        ).fetchone()
        assert row is not None, "the decision should be auditable in the alerts table"
        assert row["status"] == "suppressed"
        assert row["suppressed_by"] == "stale"
    finally:
        pipe.close()

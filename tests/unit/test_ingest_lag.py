"""Each processed message logs how late it reached us."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from structlog.testing import capture_logs

from garimpo.models.raw import RawMessage
from garimpo.pipeline import PipelineResult, _log_outcome


def test_lag_is_logged_when_telegram_date_is_known() -> None:
    now = datetime(2026, 9, 21, 12, 0, tzinfo=UTC)
    msg = RawMessage(
        source_id=1,
        tg_msg_id=1,
        text="x",
        has_media=False,
        received_at=now,
        posted_at=now - timedelta(minutes=5),
    )
    with capture_logs() as logs:
        _log_outcome(msg, PipelineResult(status="parse_failed"))
    assert logs[0]["lag_s"] == 300.0


def test_no_lag_field_without_telegram_date() -> None:
    msg = RawMessage(
        source_id=1, tg_msg_id=1, text="x", has_media=False, received_at=datetime.now(UTC)
    )
    with capture_logs() as logs:
        _log_outcome(msg, PipelineResult(status="parse_failed"))
    assert "lag_s" not in logs[0]


def test_pulse_summarises_lag_of_live_messages_only() -> None:
    from garimpo.ingest.listener import LiveStats

    stats = LiveStats()
    for lag in (2.0, 3.0, 300.0):
        stats.record("triaged_out", lag_s=lag)
    stats.record("parsed")  # recovered message: no Telegram lag known
    assert stats.drain_lag() == {"lag_p50_s": 3.0, "lag_max_s": 300.0}
    assert stats.drain_lag() == {}

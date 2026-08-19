"""Dispatcher quiet-hours deferral."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path

from garimpo.alert.channels.console import ConsoleChannel
from garimpo.alert.dispatcher import Dispatcher
from garimpo.models.alert import Level, ScoredOffer
from garimpo.models.offer import Offer, Price
from garimpo.settings import AlertLevelSettings, AlertsSettings
from garimpo.store.db import connect
from garimpo.store.repo import messages as messages_repo
from garimpo.store.repo import offers as offers_repo


def _offer_row(conn, price: float = 5799) -> tuple[int, ScoredOffer]:
    sid = messages_repo.ensure_source(conn, tg_id=1)
    rid = messages_repo.insert_raw_message(
        conn,
        source_id=sid,
        tg_msg_id=1,
        text="t",
        text_hash="h",
        has_media=False,
        received_at=datetime(2026, 8, 1, 0, 0),
        status="parsed",
    )
    offer = Offer(
        model_key="rtx_5070_ti",
        price=Price(amount=Decimal(str(price)), method="pix"),
        store="kabum",
    )
    oid = offers_repo.insert_offer(conn, raw_id=rid, offer=offer)
    scored = ScoredOffer(
        offer=offer,
        level=Level.NORMAL,
        percentile=0.1,
        baseline=6000.0,
        min_90d=5500.0,
        n_samples=20,
        price_per_pt=58.0,
        reason="test",
        rule_name="gpu",
    )
    return oid, scored


def test_normal_deferred_in_quiet_hours(tmp_path: Path) -> None:
    conn = connect(tmp_path / "t.db")
    oid, scored = _offer_row(conn)
    alerts = AlertsSettings(
        channel="console",
        normal=AlertLevelSettings(percentile=0.15, quiet_hours=[23, 8]),
        critical=AlertLevelSettings(percentile=0.03, silent=False),
    )
    d = Dispatcher(conn, ConsoleChannel(), alerts, dry_run=True)
    result = d.dispatch(scored, offer_id=oid, now=datetime(2026, 8, 1, 1, 0))
    assert result.status == "deferred"
    assert result.suppressed_by == "quiet_hours"


def test_critical_ignores_quiet_hours(tmp_path: Path) -> None:
    conn = connect(tmp_path / "t.db")
    oid, scored = _offer_row(conn)
    scored = ScoredOffer(
        offer=scored.offer,
        level=Level.CRITICAL,
        percentile=0.01,
        baseline=6000.0,
        min_90d=5500.0,
        n_samples=20,
        price_per_pt=58.0,
        reason="crit",
        rule_name="gpu",
    )
    alerts = AlertsSettings(
        channel="console",
        normal=AlertLevelSettings(percentile=0.15, quiet_hours=[23, 8]),
        critical=AlertLevelSettings(percentile=0.03, silent=False),
    )
    d = Dispatcher(conn, ConsoleChannel(), alerts, dry_run=True)
    result = d.dispatch(scored, offer_id=oid, now=datetime(2026, 8, 1, 1, 0))
    assert result.status == "dry_run"

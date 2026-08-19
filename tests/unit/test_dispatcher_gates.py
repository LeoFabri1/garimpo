"""Cooldownoldown / rate-limit gate tests."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

from garimpo.alert.cooldown import check_cooldown, check_rate_limit
from garimpo.models.alert import Level, ScoredOffer
from garimpo.models.offer import Offer, Price
from garimpo.store.db import connect
from garimpo.store.repo import alerts as alerts_repo
from garimpo.store.repo import messages as messages_repo
from garimpo.store.repo import offers as offers_repo


def _seed_alert(conn, *, model: str, price: float, sent_at: datetime) -> None:
    sid = messages_repo.ensure_source(conn, tg_id=1, username="t")
    rid = messages_repo.insert_raw_message(
        conn,
        source_id=sid,
        tg_msg_id=int(sent_at.timestamp()),
        text="x",
        text_hash=str(sent_at.timestamp()),
        has_media=False,
        received_at=sent_at,
        status="parsed",
    )
    offer = Offer(
        model_key=model,
        price=Price(amount=Decimal(str(price)), method="pix"),
        store="kabum",
    )
    oid = offers_repo.insert_offer(conn, raw_id=rid, offer=offer, created_at=sent_at)
    scored = ScoredOffer(
        offer=offer,
        level=Level.NORMAL,
        percentile=0.1,
        baseline=6000,
        min_90d=5500,
        n_samples=20,
        price_per_pt=58,
        reason="test",
        rule_name="t",
    )
    alerts_repo.insert_alert(
        conn,
        offer_id=oid,
        scored=scored,
        channel="console",
        status="sent",
        sent_at=sent_at,
    )


def test_cooldown_suppresses_same_model(tmp_path: Path) -> None:
    conn = connect(tmp_path / "t.db")
    now = datetime(2026, 8, 1, 12, 0, 0)
    _seed_alert(conn, model="rtx_5070_ti", price=5800, sent_at=now - timedelta(hours=1))
    gate = check_cooldown(
        conn, model_key="rtx_5070_ti", price=5790, now=now, cooldown_hours=6
    )
    assert gate.allow is False
    assert gate.suppressed_by == "cooldown"


def test_cooldown_override_on_drop(tmp_path: Path) -> None:
    conn = connect(tmp_path / "t.db")
    now = datetime(2026, 8, 1, 12, 0, 0)
    _seed_alert(conn, model="rtx_5070_ti", price=6000, sent_at=now - timedelta(hours=1))
    # 5% drop > 3%
    gate = check_cooldown(
        conn,
        model_key="rtx_5070_ti",
        price=5700,
        now=now,
        cooldown_hours=6,
        override_drop=0.03,
    )
    assert gate.allow is True


def test_rate_limit(tmp_path: Path) -> None:
    conn = connect(tmp_path / "t.db")
    now = datetime(2026, 8, 1, 12, 0, 0)
    for i in range(8):
        _seed_alert(
            conn,
            model=f"m{i}",
            price=5000 + i,
            sent_at=now - timedelta(minutes=i),
        )
    gate = check_rate_limit(conn, now=now, max_per_hour=8)
    assert gate.allow is False

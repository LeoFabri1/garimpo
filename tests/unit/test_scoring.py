"""Scoring scenarios from DESIGN §18.4."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from garimpo.catalog import load_gpu_catalog
from garimpo.models.alert import Level
from garimpo.models.offer import Offer, Price
from garimpo.score import HistoryPoint, WatchRule, compute_baseline, mark_outliers, score_offer


def _offer(price: float, *, confidence: float = 1.0, store: str = "kabum") -> Offer:
    return Offer(
        model_key="rtx_5070_ti",
        price=Price(amount=Decimal(str(price)), method="pix"),
        store=store,
        confidence=confidence,
    )


def _history(prices: list[float], now: datetime) -> list[HistoryPoint]:
    return [
        HistoryPoint(price=p, observed_at=now - timedelta(days=i + 1))
        for i, p in enumerate(prices)
    ]


def test_insufficient_samples_never_critical() -> None:
    now = datetime(2026, 8, 1, tzinfo=UTC)
    product = load_gpu_catalog().products["rtx_5070_ti"]
    rule = WatchRule(name="gpu", max_price=6000, models=frozenset({"rtx_5070_ti"}))
    hist = _history([5800, 5900, 6000, 6100], now)  # n=4 < 12
    scored = score_offer(
        _offer(5700),
        product=product,
        history=hist,
        rule=rule,
        now=now,
        min_samples=12,
    )
    assert scored.level != Level.CRITICAL
    assert scored.level == Level.NORMAL


def test_outlier_excluded_does_not_shift_median() -> None:
    now = datetime(2026, 8, 1, tzinfo=UTC)
    prices = [6000.0] * 20 + [500.0]  # fake listing
    hist = _history(prices, now)
    baseline = compute_baseline(hist, now, min_samples=12)
    assert baseline.kind == "ok"
    assert baseline.median is not None
    flagged = mark_outliers(hist, baseline, mad_threshold=3.0)
    assert any(p.excluded for p in flagged)
    baseline2 = compute_baseline(flagged, now, min_samples=12)
    assert baseline2.median is not None
    assert abs(baseline2.median - 6000) < 50


def test_low_trust_store_blocks_critical() -> None:
    now = datetime(2026, 8, 1, tzinfo=UTC)
    product = load_gpu_catalog().products["rtx_5070_ti"]
    rule = WatchRule(name="gpu", max_price=7000, models=frozenset({"rtx_5070_ti"}))
    # Stable history around 6300; offer at 5200 is exceptional
    hist = _history([6200 + (i % 5) * 20 for i in range(30)], now)
    scored = score_offer(
        _offer(5200, store="marketplace_generico"),
        product=product,
        history=hist,
        rule=rule,
        now=now,
        store_trust=0.6,
    )
    assert scored.level != Level.CRITICAL


def test_high_trust_low_percentile_is_critical() -> None:
    now = datetime(2026, 8, 1, tzinfo=UTC)
    product = load_gpu_catalog().products["rtx_5070_ti"]
    rule = WatchRule(name="gpu", max_price=7000, models=frozenset({"rtx_5070_ti"}))
    hist = _history([6200 + (i % 5) * 20 for i in range(40)], now)
    scored = score_offer(
        _offer(5200),
        product=product,
        history=hist,
        rule=rule,
        now=now,
        store_trust=1.0,
    )
    assert scored.level == Level.CRITICAL
    assert scored.percentile is not None
    assert scored.percentile <= 0.03

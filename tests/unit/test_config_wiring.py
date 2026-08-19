"""Config keys must reach the scoring path — a silently ignored key is a lie."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from garimpo.catalog import ModelIndex, load_gpu_catalog
from garimpo.models.alert import Level
from garimpo.models.offer import Offer, Price
from garimpo.models.raw import RawMessage
from garimpo.pipeline import Pipeline
from garimpo.score import (
    HistoryPoint,
    WatchRule,
    match_rule,
    score_offer,
    watch_rules_from_settings,
)
from garimpo.settings import Settings, WatchRuleConfig, load_settings
from garimpo.store.repo import messages as messages_repo


def _settings(tmp_path: Path) -> Settings:
    settings = load_settings(Path("config/quickstart.yaml"))
    settings.storage.path = str(tmp_path / "wiring.db")
    settings.alerts.channel = "console"
    return settings


def _offer(price: float, *, store: str = "kabum") -> Offer:
    return Offer(
        model_key="rtx_5070_ti",
        price=Price(amount=Decimal(str(price)), method="pix"),
        store=store,
        confidence=1.0,
    )


def _history(prices: list[float], now: datetime, *, day_step: int = 1) -> list[HistoryPoint]:
    return [
        HistoryPoint(price=p, observed_at=now - timedelta(days=(i + 1) * day_step))
        for i, p in enumerate(prices)
    ]


def test_alert_percentiles_reach_the_rule(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    settings.alerts.critical.percentile = 0.01
    settings.alerts.normal.percentile = 0.42
    settings.alerts.critical.min_store_trust = 0.75

    index = ModelIndex(load_gpu_catalog())
    rule = watch_rules_from_settings(settings, index)[0]

    assert rule.critical_percentile == 0.01
    assert rule.normal_percentile == 0.42
    assert rule.min_store_trust_critical == 0.75


def test_run_and_simulate_build_identical_rules(tmp_path: Path) -> None:
    """`simulate` is calibration — if it diverges from `run` it measures nothing."""
    settings = _settings(tmp_path)
    settings.alerts.critical.percentile = 0.02
    settings.alerts.normal.percentile = 0.20

    index = ModelIndex(load_gpu_catalog())
    expected = watch_rules_from_settings(settings, index)

    pipe = Pipeline(settings, dry_run=True)
    try:
        assert pipe.rules == expected
    finally:
        pipe.close()


def test_stores_exclude_is_enforced() -> None:
    rule = WatchRule(
        name="gpu",
        max_price=7000,
        models=frozenset({"rtx_5070_ti"}),
        stores_exclude=frozenset({"marketplace_generico"}),
    )
    assert match_rule("rtx_5070_ti", 97.0, [rule], "kabum") is rule
    assert match_rule("rtx_5070_ti", 97.0, [rule], "marketplace_generico") is None

    now = datetime(2026, 8, 1, tzinfo=UTC)
    product = load_gpu_catalog().products["rtx_5070_ti"]
    scored = score_offer(
        _offer(5200, store="marketplace_generico"),
        product=product,
        history=_history([6200.0] * 30, now),
        rule=rule,
        now=now,
    )
    assert scored.level == Level.IGNORE
    assert "store excluded" in scored.reason


def test_perf_tier_checked_even_when_models_set() -> None:
    strict = WatchRule(
        name="topo",
        max_price=9000,
        models=frozenset({"rtx_5070_ti"}),
        min_perf=99.0,
    )
    fallback = WatchRule(name="resto", max_price=9000)
    assert match_rule("rtx_5070_ti", 90.0, [strict, fallback]) is fallback


def test_window_days_shrinks_the_baseline() -> None:
    """Points outside scoring.window_days must not count."""
    now = datetime(2026, 8, 1, tzinfo=UTC)
    product = load_gpu_catalog().products["rtx_5070_ti"]
    rule = WatchRule(name="gpu", max_price=7000, models=frozenset({"rtx_5070_ti"}))
    # 20 points spread one per week — all inside 180d, only ~4 inside 30d.
    hist = _history([6200.0] * 20, now, day_step=7)

    wide = score_offer(
        _offer(5200), product=product, history=hist, rule=rule, now=now, window_days=180
    )
    narrow = score_offer(
        _offer(5200), product=product, history=hist, rule=rule, now=now, window_days=30
    )

    assert wide.n_samples == 20
    assert narrow.n_samples < wide.n_samples
    assert narrow.level != Level.CRITICAL  # too few samples inside the short window


def test_half_life_days_changes_the_weighting() -> None:
    now = datetime(2026, 8, 1, tzinfo=UTC)
    product = load_gpu_catalog().products["rtx_5070_ti"]
    rule = WatchRule(name="gpu", max_price=9000, models=frozenset({"rtx_5070_ti"}))
    # Prices fell recently: old expensive points, recent cheap ones.
    hist = _history([6500.0] * 15, now, day_step=6) + _history([5300.0] * 15, now)

    slow = score_offer(
        _offer(5400), product=product, history=hist, rule=rule, now=now, half_life_days=365.0
    )
    fast = score_offer(
        _offer(5400), product=product, history=hist, rule=rule, now=now, half_life_days=3.0
    )

    assert slow.percentile is not None and fast.percentile is not None
    # A short half-life leans on the recent cheap cluster, so 5400 looks worse.
    assert fast.percentile > slow.percentile


def test_explanation_reports_the_configured_window() -> None:
    """The alert text must not claim 90 days when the window is 45."""
    now = datetime(2026, 8, 1, tzinfo=UTC)
    product = load_gpu_catalog().products["rtx_5070_ti"]
    rule = WatchRule(name="gpu", max_price=9000, models=frozenset({"rtx_5070_ti"}))
    scored = score_offer(
        _offer(5200),
        product=product,
        history=_history([6200.0] * 30, now),
        rule=rule,
        now=now,
        window_days=45,
    )
    assert "45 dias" in scored.reason
    assert "90 dias" not in scored.reason


def test_retention_purges_noise_and_keeps_parsed(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    settings.storage.retention_raw_days = 7
    pipe = Pipeline(settings, dry_run=True)
    try:
        old = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=30)
        source_id = messages_repo.ensure_source(
            pipe.conn, tg_id=1, username="test", parser="generic"
        )
        for i, status in enumerate(["triaged_out", "duplicate", "parsed"]):
            messages_repo.insert_raw_message(
                pipe.conn,
                source_id=source_id,
                tg_msg_id=1000 + i,
                text="ruido",
                text_hash=f"hash{i}",
                has_media=False,
                received_at=old,
                status=status,
            )

        removed = pipe.purge_expired()

        assert removed == 2
        remaining = messages_repo.count_by_status(pipe.conn)
        assert "triaged_out" not in remaining
        assert "duplicate" not in remaining
        assert remaining.get("parsed") == 1
    finally:
        pipe.close()


def test_retention_keeps_rows_inside_the_window(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    settings.storage.retention_raw_days = 90
    pipe = Pipeline(settings, dry_run=True)
    try:
        recent = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=30)
        source_id = messages_repo.ensure_source(
            pipe.conn, tg_id=1, username="test", parser="generic"
        )
        messages_repo.insert_raw_message(
            pipe.conn,
            source_id=source_id,
            tg_msg_id=2000,
            text="ruido",
            text_hash="hashrecent",
            has_media=False,
            received_at=recent,
            status="triaged_out",
        )
        assert pipe.purge_expired() == 0
    finally:
        pipe.close()


def test_perf_tier_parsing_reaches_the_rule(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    settings.watch = [WatchRuleConfig(name="topo", perf_tier=">= 97", max_price=6000)]
    index = ModelIndex(load_gpu_catalog())
    assert watch_rules_from_settings(settings, index)[0].min_perf == 97.0


def test_pipeline_respects_configured_window(tmp_path: Path) -> None:
    """scoring.window_days must survive the trip through Pipeline.process."""
    settings = _settings(tmp_path)
    settings.scoring.window_days = 1
    settings.scoring.min_samples = 2

    pipe = Pipeline(settings, dry_run=True)
    try:
        from garimpo.store.repo import history as history_repo

        old = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=60)
        for i in range(20):
            history_repo.insert_history(
                pipe.conn,
                model_key="rtx_5070_ti",
                price=6200.0,
                observed_at=old - timedelta(days=i),
                origin="backfill",
                condition="new",
                store="kabum",
                offer_id=None,
            )
        result = pipe.process(
            RawMessage(
                source_id=1,
                tg_msg_id=7001,
                text="RTX 5070 Ti ASUS — R$ 5.799 no PIX Kabum",
                has_media=False,
                received_at=datetime.now(UTC),
                source_username="test",
            )
        )
        # All 20 points are 60+ days old, so a 1-day window sees only the new offer.
        assert result.scored is not None
        assert result.scored.n_samples <= 1
    finally:
        pipe.close()

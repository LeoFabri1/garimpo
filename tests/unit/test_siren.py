"""A rule can demand every offer under its ceiling (`always_alert`) and ring a
siren on the phone (`siren`) — the RTX 5090 hunt, where the percentile is
too picky and a Telegram ping is too easy to sleep through."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from garimpo.alert.channels.bark import BarkChannel
from garimpo.alert.channels.factory import build_siren
from garimpo.alert.dispatcher import Dispatcher
from garimpo.catalog import ModelIndex, load_catalog_for_watch, load_gpu_catalog
from garimpo.models.alert import Level, ScoredOffer
from garimpo.models.offer import Offer, Price
from garimpo.score import HistoryPoint
from garimpo.score.config import watch_rules_from_settings
from garimpo.score.rules import WatchRule, score_offer
from garimpo.settings import AlertLevelSettings, AlertsSettings, Settings
from garimpo.store.db import connect
from garimpo.store.repo import messages as messages_repo
from garimpo.store.repo import offers as offers_repo

NOW = datetime(2026, 9, 26, tzinfo=UTC)
PRODUCT = load_gpu_catalog().products["rtx_5090"]


def _offer(price: float) -> Offer:
    return Offer(
        model_key="rtx_5090",
        price=Price(amount=Decimal(str(price)), method="pix"),
        store="kabum",
        url="https://kabum.example/5090",
    )


def _history() -> list[HistoryPoint]:
    # 20 samples at 22–23k: 24.9k sits far above the 15th percentile.
    return [
        HistoryPoint(price=22000 + 50 * i, observed_at=NOW - timedelta(days=i + 1))
        for i in range(20)
    ]


def _score(rule: WatchRule, price: float) -> ScoredOffer:
    return score_offer(_offer(price), product=PRODUCT, history=_history(), rule=rule, now=NOW)


def test_percentile_alone_ignores_an_offer_under_the_ceiling() -> None:
    rule = WatchRule(name="gpu-5090", max_price=25000, models=frozenset({"rtx_5090"}))
    assert _score(rule, 24900).level == Level.IGNORE


def test_always_alert_floors_an_offer_under_the_ceiling_to_normal() -> None:
    rule = WatchRule(
        name="gpu-5090", max_price=25000, models=frozenset({"rtx_5090"}), always_alert=True
    )
    assert _score(rule, 24900).level == Level.NORMAL


def test_always_alert_keeps_a_critical_price_critical() -> None:
    rule = WatchRule(
        name="gpu-5090", max_price=25000, models=frozenset({"rtx_5090"}), always_alert=True
    )
    assert _score(rule, 19000).level == Level.CRITICAL


def test_always_alert_still_respects_the_ceiling() -> None:
    rule = WatchRule(
        name="gpu-5090", max_price=25000, models=frozenset({"rtx_5090"}), always_alert=True
    )
    assert _score(rule, 25100).level == Level.IGNORE


class _Recorder:
    def __init__(self, name: str) -> None:
        self.name = name
        self.sent: list[str] = []

    def send(self, scored: ScoredOffer, *, silent: bool = False) -> None:
        self.sent.append(scored.offer.model_key)


class _Broken:
    name = "broken"

    def send(self, scored: ScoredOffer, *, silent: bool = False) -> None:
        raise httpx.ConnectError("bark fora do ar")


def _dispatch(
    tmp_path: Path,
    scored: ScoredOffer,
    *,
    siren: object | None,
    max_per_hour: int = 8,
    prior_alerts: int = 0,
):  # type: ignore[no-untyped-def]
    conn = connect(tmp_path / "t.db")
    sid = messages_repo.ensure_source(conn, tg_id=1)
    alerts = AlertsSettings(
        channel="console",
        normal=AlertLevelSettings(percentile=0.15, silent=True),
        critical=AlertLevelSettings(percentile=0.03, silent=False),
        max_per_hour=max_per_hour,
    )
    channel = _Recorder("main")
    dispatcher = Dispatcher(conn, channel, alerts, siren=siren)  # type: ignore[arg-type]
    now = datetime(2026, 9, 26, 12, 0)
    oid = 0
    for i in range(prior_alerts + 1):
        # Distinct models so cooldown never kicks in; only the rate limit can.
        offer = scored.offer if i == prior_alerts else Offer(
            model_key=f"filler_{i}", price=Price(amount=Decimal("100"))
        )
        rid = messages_repo.insert_raw_message(
            conn,
            source_id=sid,
            tg_msg_id=i + 1,
            text="t",
            text_hash=f"h{i}",
            has_media=False,
            received_at=now,
            status="parsed",
        )
        oid = offers_repo.insert_offer(conn, raw_id=rid, offer=offer)
        if i < prior_alerts:
            filler = ScoredOffer(
                offer=offer,
                level=Level.NORMAL,
                percentile=None,
                baseline=None,
                min_90d=None,
                n_samples=0,
                price_per_pt=None,
                reason="x",
                rule_name="other",
            )
            dispatcher.dispatch(filler, offer_id=oid, now=now)
    result = dispatcher.dispatch(scored, offer_id=oid, now=now)
    return result, channel


def _siren_rule(**kw: object) -> WatchRule:
    return WatchRule(
        name="gpu-5090",
        max_price=25000,
        models=frozenset({"rtx_5090"}),
        always_alert=True,
        siren=True,
        silent=False,
        **kw,  # type: ignore[arg-type]
    )


def test_siren_rule_sends_to_telegram_and_siren(tmp_path: Path) -> None:
    siren = _Recorder("siren")
    result, channel = _dispatch(tmp_path, _score(_siren_rule(), 24900), siren=siren)
    assert result.status == "sent"
    assert channel.sent == ["rtx_5090"]
    assert siren.sent == ["rtx_5090"]


def test_rule_without_siren_does_not_ring_it(tmp_path: Path) -> None:
    siren = _Recorder("siren")
    rule = WatchRule(name="gpu-5090", max_price=25000, always_alert=True)
    _dispatch(tmp_path, _score(rule, 24900), siren=siren)
    assert siren.sent == []


def test_siren_failure_does_not_block_telegram(tmp_path: Path) -> None:
    result, channel = _dispatch(tmp_path, _score(_siren_rule(), 24900), siren=_Broken())
    assert result.status == "sent"
    assert channel.sent == ["rtx_5090"]


def test_always_alert_rule_is_not_rate_limited(tmp_path: Path) -> None:
    siren = _Recorder("siren")
    result, channel = _dispatch(
        tmp_path,
        _score(_siren_rule(), 24900),
        siren=siren,
        max_per_hour=2,
        prior_alerts=2,
    )
    assert result.status == "sent"
    assert channel.sent[-1] == "rtx_5090"
    assert siren.sent == ["rtx_5090"]


def test_config_flags_reach_the_rule() -> None:
    settings = Settings.model_validate(
        {
            "watch": [
                {
                    "name": "gpu-5090",
                    "models": ["RTX 5090"],
                    "max_price": 25000,
                    "always_alert": True,
                    "siren": True,
                },
                {"name": "other", "max_price": 5000},
            ]
        }
    )
    loud, other = watch_rules_from_settings(settings, ModelIndex(load_catalog_for_watch(["gpu"])))
    assert (loud.always_alert, loud.siren) == (True, True)
    assert (other.always_alert, other.siren) == (False, False)


def test_bark_posts_a_critical_repeating_push() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"code": 200, "message": "success"})

    bark = BarkChannel(
        key="DEVKEY", server="https://bark.example", transport=httpx.MockTransport(handler)
    )
    bark.send(_score(_siren_rule(), 24900))

    (req,) = captured
    assert str(req.url) == "https://bark.example/push"
    body = json.loads(req.content)
    assert body["device_key"] == "DEVKEY"
    assert body["level"] == "critical"
    assert body["call"] == "1"
    assert body["volume"] == 10
    assert body["url"] == "https://kabum.example/5090"
    assert "24900" in body["title"]


def test_bark_raises_on_api_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"code": 400, "message": "device key not found"})

    bark = BarkChannel(
        key="X", server="https://bark.example", transport=httpx.MockTransport(handler)
    )
    with pytest.raises(RuntimeError, match="device key"):
        bark.send(_score(_siren_rule(), 24900))


def test_build_siren_needs_the_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BARK_KEY", raising=False)
    assert build_siren(Settings()) is None
    monkeypatch.setenv("BARK_KEY", "abc")
    siren = build_siren(Settings())
    assert isinstance(siren, BarkChannel)

"""A watch rule can override the level's `silent`: the RAM kit rings even as
a NORMAL alert, and a loud rule is not held back by quiet hours."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path

from garimpo.alert.dispatcher import Dispatcher
from garimpo.catalog import ModelIndex, load_catalog_for_watch
from garimpo.models.alert import Level, ScoredOffer
from garimpo.models.catalog import Product
from garimpo.models.offer import Offer, Price
from garimpo.score.config import watch_rules_from_settings
from garimpo.score.rules import WatchRule, score_offer
from garimpo.settings import AlertLevelSettings, AlertsSettings, Settings
from garimpo.store.db import connect
from garimpo.store.repo import messages as messages_repo
from garimpo.store.repo import offers as offers_repo


class _Recorder:
    name = "recorder"

    def __init__(self) -> None:
        self.sent: list[tuple[str, bool]] = []

    def send(self, scored: ScoredOffer, *, silent: bool = False) -> None:
        self.sent.append((scored.offer.model_key, silent))


PRODUCT = Product(
    key="ddr5_64gb_2x32_kit",
    display="Kit",
    vendor="any",
    perf=100.0,
    aliases=("2x32gb",),
    negative_aliases=(),
)


def _scored(rule: WatchRule) -> ScoredOffer:
    offer = Offer(model_key=PRODUCT.key, price=Price(amount=Decimal("2999")))
    # Empty history: the "insufficient" branch, which yields a NORMAL alert.
    return score_offer(offer, product=PRODUCT, history=[], rule=rule, now=datetime(2026, 9, 21))


def _dispatch(tmp_path: Path, scored: ScoredOffer, *, quiet: list[int] | None = None):  # type: ignore[no-untyped-def]
    conn = connect(tmp_path / "t.db")
    sid = messages_repo.ensure_source(conn, tg_id=1)
    rid = messages_repo.insert_raw_message(
        conn,
        source_id=sid,
        tg_msg_id=1,
        text="t",
        text_hash="h",
        has_media=False,
        received_at=datetime(2026, 9, 21, 3, 0),
        status="parsed",
    )
    oid = offers_repo.insert_offer(conn, raw_id=rid, offer=scored.offer)
    alerts = AlertsSettings(
        channel="console",
        normal=AlertLevelSettings(percentile=0.15, silent=True, quiet_hours=quiet),
        critical=AlertLevelSettings(percentile=0.01, silent=False),
    )
    channel = _Recorder()
    result = Dispatcher(conn, channel, alerts).dispatch(
        scored, offer_id=oid, now=datetime(2026, 9, 21, 3, 0)
    )
    return result, channel


def test_loud_rule_rings_on_a_normal_alert(tmp_path: Path) -> None:
    scored = _scored(WatchRule(name="ram-64-kit", max_price=4000, silent=False))
    assert scored.level == Level.NORMAL
    _, channel = _dispatch(tmp_path, scored)
    assert channel.sent == [(PRODUCT.key, False)]


def test_rule_without_silent_keeps_the_level_default(tmp_path: Path) -> None:
    scored = _scored(WatchRule(name="ram-16", max_price=4000))
    _, channel = _dispatch(tmp_path, scored)
    assert channel.sent == [(PRODUCT.key, True)]


def test_loud_rule_is_not_deferred_by_quiet_hours(tmp_path: Path) -> None:
    scored = _scored(WatchRule(name="ram-64-kit", max_price=4000, silent=False))
    result, channel = _dispatch(tmp_path, scored, quiet=[23, 8])
    assert result.status == "sent"
    assert channel.sent == [(PRODUCT.key, False)]


def test_quiet_hours_still_hold_a_default_rule(tmp_path: Path) -> None:
    scored = _scored(WatchRule(name="ram-16", max_price=4000))
    result, channel = _dispatch(tmp_path, scored, quiet=[23, 8])
    assert result.status == "deferred"
    assert channel.sent == []


def test_config_silent_reaches_the_rule() -> None:
    settings = Settings.model_validate(
        {
            "watch": [
                {"name": "loud", "category": "ram", "max_price": 4000, "silent": False},
                {"name": "default", "category": "ram", "max_price": 4000},
            ]
        }
    )
    index = ModelIndex(load_catalog_for_watch(["ram"]))
    loud, default = watch_rules_from_settings(settings, index)
    assert loud.silent is False
    assert default.silent is None

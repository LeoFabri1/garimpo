"""Alert dispatcher: cooldown → rate limit → channel.send (DESIGN §12.1)."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime

from garimpo.alert.channels.base import Channel
from garimpo.alert.cooldown import check_cooldown, check_rate_limit
from garimpo.models.alert import Level, ScoredOffer
from garimpo.settings import AlertsSettings
from garimpo.store.repo import alerts as alerts_repo


@dataclass(frozen=True, slots=True)
class DispatchResult:
    status: str  # sent | dry_run | suppressed
    suppressed_by: str | None = None
    detail: str | None = None


class Dispatcher:
    def __init__(
        self,
        conn: sqlite3.Connection,
        channel: Channel,
        alerts: AlertsSettings,
        *,
        dry_run: bool = False,
    ) -> None:
        self.conn = conn
        self.channel = channel
        self.alerts = alerts
        self.dry_run = dry_run

    def dispatch(
        self,
        scored: ScoredOffer,
        *,
        offer_id: int,
        now: datetime,
    ) -> DispatchResult:
        if scored.level == Level.IGNORE:
            return DispatchResult(status="suppressed", suppressed_by="ignore")

        cool = check_cooldown(
            self.conn,
            model_key=scored.offer.model_key,
            price=float(scored.offer.price.amount),
            now=now,
            cooldown_hours=self.alerts.cooldown_hours,
            override_drop=self.alerts.cooldown_override_drop,
        )
        if not cool.allow:
            alerts_repo.insert_alert(
                self.conn,
                offer_id=offer_id,
                scored=scored,
                channel=self.channel.name,
                status="suppressed",
                suppressed_by=cool.suppressed_by,
                sent_at=now,
            )
            return DispatchResult(
                status="suppressed",
                suppressed_by=cool.suppressed_by,
                detail=cool.detail,
            )

        rate = check_rate_limit(
            self.conn, now=now, max_per_hour=self.alerts.max_per_hour
        )
        if not rate.allow:
            alerts_repo.insert_alert(
                self.conn,
                offer_id=offer_id,
                scored=scored,
                channel=self.channel.name,
                status="suppressed",
                suppressed_by=rate.suppressed_by,
                sent_at=now,
            )
            # One diagnostic message when rate limit trips
            try:
                self.channel.send(
                    _rate_limit_notice(scored, rate.detail or ""),
                    silent=False,
                )
            except Exception:  # noqa: BLE001
                pass
            return DispatchResult(
                status="suppressed",
                suppressed_by=rate.suppressed_by,
                detail=rate.detail,
            )

        silent = (
            self.alerts.critical.silent
            if scored.level == Level.CRITICAL
            else self.alerts.normal.silent
        )
        self.channel.send(scored, silent=silent)
        status = "dry_run" if self.dry_run else "sent"
        alerts_repo.insert_alert(
            self.conn,
            offer_id=offer_id,
            scored=scored,
            channel=self.channel.name,
            status=status,
            sent_at=now,
        )
        return DispatchResult(status=status)


def _rate_limit_notice(scored: ScoredOffer, detail: str) -> ScoredOffer:
    """Reuse ScoredOffer shape so Channel.send stays simple."""
    from garimpo.models.offer import Offer, Price

    notice = Offer(
        model_key="rate_limit",
        price=Price(amount=scored.offer.price.amount),
        confidence=1.0,
    )
    return ScoredOffer(
        offer=notice,
        level=Level.NORMAL,
        percentile=None,
        baseline=None,
        min_90d=None,
        n_samples=0,
        price_per_pt=None,
        reason=(
            f"⚠️ Rate limit: {detail}. Config provavelmente frouxa. "
            "Rode: garimpo simulate --days 30 (quando disponível)"
        ),
        rule_name="system",
    )

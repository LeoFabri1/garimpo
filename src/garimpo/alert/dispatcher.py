"""Alert dispatcher: cooldown → rate limit → quiet hours → channel.send."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime

from garimpo.alert.channels.base import Channel
from garimpo.alert.cooldown import check_cooldown, check_rate_limit
from garimpo.alert.quiet import in_quiet_hours
from garimpo.models.alert import Level, ScoredOffer
from garimpo.settings import AlertsSettings
from garimpo.store.repo import alerts as alerts_repo


@dataclass(frozen=True, slots=True)
class DispatchResult:
    status: str  # sent | dry_run | suppressed | deferred
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

        # Quiet hours: only for NORMAL (critical always sends)
        quiet = self.alerts.normal.quiet_hours
        if scored.level == Level.NORMAL and in_quiet_hours(now, quiet):
            alerts_repo.insert_alert(
                self.conn,
                offer_id=offer_id,
                scored=scored,
                channel=self.channel.name,
                status="deferred",
                suppressed_by="quiet_hours",
                sent_at=None,
            )
            return DispatchResult(
                status="deferred",
                suppressed_by="quiet_hours",
                detail="normal alert deferred until quiet hours end",
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

    def flush_deferred(self, *, now: datetime | None = None) -> int:
        """Send a single digest for deferred normal alerts and mark them sent."""
        now = now or datetime.now()
        rows = self.conn.execute(
            """
            SELECT a.id, a.offer_id, a.reason, o.model_key, o.price, o.store,
                   o.coupon, o.url
            FROM alerts a
            JOIN offers o ON o.id = a.offer_id
            WHERE a.status = 'deferred'
            ORDER BY a.id ASC
            """
        ).fetchall()
        if not rows:
            return 0

        lines = [f"🌅 {len(rows)} oferta(s) passaram do filtro durante quiet hours", ""]
        for r in rows[:20]:
            store = r["store"] or "?"
            line = f"{r['model_key']} — R$ {r['price']:.0f} ({store})"
            if r["coupon"]:
                line += f" · cupom {r['coupon']}"
            lines.append(line)
            if r["url"]:
                lines.append(f"🔗 {r['url']}")
        if len(rows) > 20:
            lines.append(f"… e mais {len(rows) - 20}")

        text = "\n".join(lines)
        _send_raw(self.channel, text, silent=True)

        ids = [int(r["id"]) for r in rows]
        self.conn.execute(
            f"""
            UPDATE alerts SET status = ?, sent_at = ?
            WHERE id IN ({",".join("?" * len(ids))})
            """,
            ["sent", now.replace(microsecond=0).isoformat(), *ids],
        )
        self.conn.commit()
        return len(rows)


def _send_raw(channel: Channel, text: str, *, silent: bool) -> None:
    from decimal import Decimal

    from garimpo.models.offer import Offer, Price

    scored = ScoredOffer(
        offer=Offer(model_key="digest", price=Price(amount=Decimal("0"))),
        level=Level.NORMAL,
        percentile=None,
        baseline=None,
        min_90d=None,
        n_samples=0,
        price_per_pt=None,
        reason=text,
        rule_name="system",
    )
    channel.send(scored, silent=silent)


def _rate_limit_notice(scored: ScoredOffer, detail: str) -> ScoredOffer:
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

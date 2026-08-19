"""Replay history against watch rules (calibration)."""

from __future__ import annotations

import sqlite3
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from garimpo.catalog import ModelIndex, load_gpu_catalog
from garimpo.models.offer import Offer, Price
from garimpo.score import HistoryPoint, match_rule, score_offer, watch_rules_from_settings
from garimpo.settings import Settings
from garimpo.store.db import connect


@dataclass
class SimulateReport:
    days: int
    offers: int
    by_level: dict[str, int]


def simulate(settings: Settings, *, days: int = 90) -> SimulateReport:
    catalog = load_gpu_catalog()
    index = ModelIndex(catalog)
    rules = watch_rules_from_settings(settings, index)
    conn = connect(settings.storage.path)
    try:
        since = (
            datetime.now(UTC).replace(tzinfo=None) - timedelta(days=days)
        ).isoformat()
        rows = conn.execute(
            """
            SELECT model_key, price, store, condition, created_at, confidence
            FROM offers
            WHERE created_at >= ?
            ORDER BY created_at ASC
            """,
            (since,),
        ).fetchall()
        counts: Counter[str] = Counter()
        for r in rows:
            product = catalog.products.get(r["model_key"])
            if product is None:
                continue
            offer = Offer(
                model_key=r["model_key"],
                price=Price(amount=Decimal(str(r["price"])), method="unknown"),
                store=r["store"],
                condition=r["condition"] or "new",
                confidence=float(r["confidence"] or 1.0),
            )
            try:
                now = datetime.fromisoformat(r["created_at"])
            except ValueError:
                continue
            hist = _history(conn, offer.model_key, before=now)
            matched = match_rule(offer.model_key, product.perf, rules, offer.store)
            if matched is None:
                counts["ignore"] += 1
                continue
            scored = score_offer(
                offer,
                product=product,
                history=hist,
                rule=matched,
                now=now,
                store_trust=1.0,
                min_samples=settings.scoring.min_samples,
                window_days=settings.scoring.window_days,
                half_life_days=settings.scoring.half_life_days,
            )
            counts[scored.level.value] += 1
        return SimulateReport(
            days=days,
            offers=len(rows),
            by_level=dict(counts),
        )
    finally:
        conn.close()


def _history(
    conn: sqlite3.Connection, model_key: str, *, before: datetime
) -> list[HistoryPoint]:
    rows = conn.execute(
        """
        SELECT price, observed_at, excluded FROM price_history
        WHERE model_key = ? AND observed_at < ?
        """,
        (model_key, before.isoformat()),
    ).fetchall()
    out = []
    for r in rows:
        try:
            observed = datetime.fromisoformat(r["observed_at"])
        except ValueError:
            continue
        out.append(
            HistoryPoint(
                price=float(r["price"]),
                observed_at=observed,
                excluded=bool(r["excluded"]),
            )
        )
    return out

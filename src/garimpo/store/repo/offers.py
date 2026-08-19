"""Offers repository."""

from __future__ import annotations

import hashlib
import sqlite3
from datetime import UTC, datetime
from decimal import Decimal

from garimpo.models.offer import Offer


def offer_hash(model_key: str, price: Decimal | float, store: str | None) -> str:
    # round to nearest 10 BRL so cent-level noise still dedupes
    rounded = int(round(float(price), -1))
    payload = f"{model_key}|{rounded}|{store or ''}"
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def insert_offer(
    conn: sqlite3.Connection,
    *,
    raw_id: int,
    offer: Offer,
    created_at: datetime | None = None,
) -> int:
    created = created_at or datetime.now(UTC).replace(tzinfo=None)
    ohash = offer_hash(offer.model_key, offer.price.amount, offer.store)
    coupon = offer.coupon.code if offer.coupon else None
    listed = float(offer.price.listed) if offer.price.listed is not None else None
    cur = conn.execute(
        """
        INSERT INTO offers (
            raw_id, model_key, brand, variant, condition,
            price, price_listed, price_method, installments, coupon,
            store, url, url_resolved, offer_hash, extracted_by,
            confidence, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            raw_id,
            offer.model_key,
            offer.brand,
            offer.variant,
            offer.condition,
            float(offer.price.amount),
            listed,
            offer.price.method,
            offer.price.installments,
            coupon,
            offer.store,
            offer.url,
            None,
            ohash,
            offer.extracted_by,
            offer.confidence,
            created.replace(microsecond=0).isoformat(),
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def recent_offer_hash_exists(
    conn: sqlite3.Connection,
    ohash: str,
    *,
    within_minutes: int = 10,
    now: datetime | None = None,
) -> bool:
    now = now or datetime.now(UTC).replace(tzinfo=None)
    rows = conn.execute(
        """
        SELECT created_at FROM offers
        WHERE offer_hash = ?
        ORDER BY id DESC LIMIT 5
        """,
        (ohash,),
    ).fetchall()
    for r in rows:
        try:
            created = datetime.fromisoformat(r["created_at"])
        except ValueError:
            continue
        if 0 <= (now - created).total_seconds() <= within_minutes * 60:
            return True
    return False

"""Cooldownoldown and rate-limit decisions (DESIGN §10.3 / §12)."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True, slots=True)
class GateResult:
    allow: bool
    suppressed_by: str | None = None
    detail: str | None = None


def check_cooldown(
    conn: sqlite3.Connection,
    *,
    model_key: str,
    price: float,
    now: datetime,
    cooldown_hours: float = 6.0,
    override_drop: float = 0.03,
) -> GateResult:
    """Same model_key within window → suppress, unless price dropped >= override_drop."""
    row = conn.execute(
        """
        SELECT a.sent_at, o.price
        FROM alerts a
        JOIN offers o ON o.id = a.offer_id
        WHERE o.model_key = ?
          AND a.status IN ('sent', 'dry_run')
          AND a.level IN ('critical', 'normal')
        ORDER BY a.id DESC
        LIMIT 1
        """,
        (model_key,),
    ).fetchone()
    if row is None or row["sent_at"] is None:
        return GateResult(allow=True)

    try:
        last_at = datetime.fromisoformat(row["sent_at"])
    except ValueError:
        return GateResult(allow=True)

    if now - last_at > timedelta(hours=cooldown_hours):
        return GateResult(allow=True)

    last_price = float(row["price"])
    if last_price > 0 and (last_price - price) / last_price >= override_drop:
        return GateResult(allow=True, detail="cooldown override: price drop")

    return GateResult(
        allow=False,
        suppressed_by="cooldown",
        detail=f"mesmo modelo há {(now - last_at).total_seconds() / 3600:.1f}h",
    )


def check_rate_limit(
    conn: sqlite3.Connection,
    *,
    now: datetime,
    max_per_hour: int = 8,
) -> GateResult:
    since = (now - timedelta(hours=1)).isoformat()
    row = conn.execute(
        """
        SELECT COUNT(*) AS n FROM alerts
        WHERE status IN ('sent', 'dry_run')
          AND sent_at IS NOT NULL
          AND sent_at >= ?
        """,
        (since,),
    ).fetchone()
    n = int(row["n"]) if row else 0
    if n >= max_per_hour:
        return GateResult(
            allow=False,
            suppressed_by="rate_limit",
            detail=f"{n} alertas na última hora (max {max_per_hour})",
        )
    return GateResult(allow=True)

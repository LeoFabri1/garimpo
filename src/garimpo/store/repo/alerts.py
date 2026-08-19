"""Alerts repository."""

from __future__ import annotations

import sqlite3
from datetime import datetime

from garimpo.models.alert import ScoredOffer


def insert_alert(
    conn: sqlite3.Connection,
    *,
    offer_id: int,
    scored: ScoredOffer,
    channel: str,
    status: str,
    suppressed_by: str | None = None,
    sent_at: datetime | None = None,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO alerts (
            offer_id, rule_name, level, percentile, baseline, min_90d,
            n_samples, price_per_pt, reason, channel, status,
            suppressed_by, sent_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            offer_id,
            scored.rule_name,
            scored.level.value,
            scored.percentile,
            scored.baseline,
            scored.min_90d,
            scored.n_samples,
            scored.price_per_pt,
            scored.reason,
            channel,
            status,
            suppressed_by,
            sent_at.replace(microsecond=0).isoformat() if sent_at else None,
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def count_alerts(conn: sqlite3.Connection) -> dict[str, int]:
    rows = conn.execute(
        "SELECT level, COUNT(*) AS n FROM alerts GROUP BY level"
    ).fetchall()
    return {str(r["level"]): int(r["n"]) for r in rows}

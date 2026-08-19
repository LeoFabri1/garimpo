"""Price history repository."""

from __future__ import annotations

import sqlite3
from datetime import datetime

from garimpo.score.baseline import HistoryPoint


def insert_history(
    conn: sqlite3.Connection,
    *,
    model_key: str,
    price: float,
    observed_at: datetime,
    origin: str,
    condition: str = "new",
    store: str | None = None,
    offer_id: int | None = None,
    excluded: bool = False,
) -> int | None:
    try:
        cur = conn.execute(
            """
            INSERT INTO price_history (
                model_key, price, condition, store, observed_at,
                origin, offer_id, excluded
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                model_key,
                price,
                condition,
                store,
                observed_at.replace(microsecond=0).isoformat(),
                origin,
                offer_id,
                1 if excluded else 0,
            ),
        )
        conn.commit()
        return int(cur.lastrowid)
    except sqlite3.IntegrityError:
        return None


def load_history(
    conn: sqlite3.Connection,
    model_key: str,
    *,
    condition: str = "new",
    days: int = 90,
) -> list[HistoryPoint]:
    rows = conn.execute(
        """
        SELECT price, observed_at, excluded
        FROM price_history
        WHERE model_key = ? AND condition = ?
        ORDER BY observed_at DESC
        """,
        (model_key, condition),
    ).fetchall()
    points: list[HistoryPoint] = []
    for r in rows:
        try:
            observed = datetime.fromisoformat(r["observed_at"])
        except ValueError:
            continue
        points.append(
            HistoryPoint(
                price=float(r["price"]),
                observed_at=observed,
                excluded=bool(r["excluded"]),
            )
        )
    return points


def count_history(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COUNT(*) AS n FROM price_history").fetchone()
    return int(row["n"])

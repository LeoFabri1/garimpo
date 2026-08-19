"""Read-only query helpers for MCP / panel / export (SQLite mode=ro)."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from garimpo.catalog import ModelIndex, load_gpu_catalog
from garimpo.store.db import connect


def open_ro(path: str | Path) -> sqlite3.Connection:
    return connect(path, read_only=True)


def query_price_history(
    db_path: str | Path,
    model: str,
    *,
    days: int = 90,
    condition: str = "new",
) -> dict[str, Any]:
    conn = open_ro(db_path)
    try:
        since = (datetime.now(UTC).replace(tzinfo=None) - timedelta(days=days)).isoformat()
        rows = conn.execute(
            """
            SELECT price, store, observed_at, origin
            FROM price_history
            WHERE model_key = ? AND condition = ? AND excluded = 0
              AND observed_at >= ?
            ORDER BY observed_at ASC
            """,
            (model, condition, since),
        ).fetchall()
        prices = [float(r["price"]) for r in rows]
        series = [
            {
                "price": float(r["price"]),
                "store": r["store"],
                "observed_at": r["observed_at"],
                "origin": r["origin"],
            }
            for r in rows
        ]
        if not prices:
            return {"model": model, "n": 0, "series": [], "median": None, "min": None, "max": None}
        prices_sorted = sorted(prices)
        mid = len(prices_sorted) // 2
        median = (
            prices_sorted[mid]
            if len(prices_sorted) % 2
            else (prices_sorted[mid - 1] + prices_sorted[mid]) / 2
        )
        return {
            "model": model,
            "n": len(prices),
            "median": median,
            "min": min(prices),
            "max": max(prices),
            "series": series,
        }
    finally:
        conn.close()


def list_offers(
    db_path: str | Path,
    *,
    days: int = 30,
    model: str | None = None,
) -> list[dict[str, Any]]:
    conn = open_ro(db_path)
    try:
        since = (datetime.now(UTC).replace(tzinfo=None) - timedelta(days=days)).isoformat()
        if model:
            rows = conn.execute(
                """
                SELECT id, model_key, price, store, created_at, confidence
                FROM offers WHERE created_at >= ? AND model_key = ?
                ORDER BY created_at DESC LIMIT 200
                """,
                (since, model),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, model_key, price, store, created_at, confidence
                FROM offers WHERE created_at >= ?
                ORDER BY created_at DESC LIMIT 200
                """,
                (since,),
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def list_alerts(
    db_path: str | Path,
    *,
    days: int = 30,
    level: str | None = None,
) -> list[dict[str, Any]]:
    conn = open_ro(db_path)
    try:
        since = (datetime.now(UTC).replace(tzinfo=None) - timedelta(days=days)).isoformat()
        if level:
            rows = conn.execute(
                """
                SELECT id, offer_id, level, reason, status, suppressed_by, sent_at, channel
                FROM alerts
                WHERE (sent_at >= ? OR sent_at IS NULL) AND level = ?
                ORDER BY id DESC LIMIT 200
                """,
                (since, level),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, offer_id, level, reason, status, suppressed_by, sent_at, channel
                FROM alerts
                WHERE sent_at >= ? OR status = 'deferred'
                ORDER BY id DESC LIMIT 200
                """,
                (since,),
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def list_suppressed(db_path: str | Path, *, days: int = 30) -> list[dict[str, Any]]:
    conn = open_ro(db_path)
    try:
        since = (datetime.now(UTC).replace(tzinfo=None) - timedelta(days=days)).isoformat()
        rows = conn.execute(
            """
            SELECT id, offer_id, level, reason, status, suppressed_by, sent_at
            FROM alerts
            WHERE status = 'suppressed' AND sent_at >= ?
            ORDER BY id DESC LIMIT 200
            """,
            (since,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def parse_stats(db_path: str | Path, *, days: int = 30) -> dict[str, Any]:
    conn = open_ro(db_path)
    try:
        since = (datetime.now(UTC).replace(tzinfo=None) - timedelta(days=days)).isoformat()
        rows = conn.execute(
            """
            SELECT status, COUNT(*) AS n
            FROM raw_messages WHERE received_at >= ?
            GROUP BY status
            """,
            (since,),
        ).fetchall()
        return {str(r["status"]): int(r["n"]) for r in rows}
    finally:
        conn.close()


def catalog_lookup(query: str) -> dict[str, Any] | None:
    index = ModelIndex(load_gpu_catalog())
    hit = index.resolve(query)
    if hit is None:
        return None
    product = index.get(hit.model_key)
    assert product is not None
    return {
        "model_key": hit.model_key,
        "display": product.display,
        "confidence": hit.confidence,
        "method": hit.method,
        "matched_alias": hit.matched_alias,
    }


def export_price_history_csv(db_path: str | Path, out_path: Path) -> int:
    import csv

    conn = open_ro(db_path)
    try:
        rows = conn.execute(
            """
            SELECT model_key, price, store, observed_at, condition, origin
            FROM price_history ORDER BY observed_at ASC
            """
        ).fetchall()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(
                fh,
                fieldnames=["model_key", "price", "store", "observed_at", "condition", "origin"],
            )
            writer.writeheader()
            for r in rows:
                writer.writerow(dict(r))
        return len(rows)
    finally:
        conn.close()


def dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, default=str)

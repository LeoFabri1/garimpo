"""Enrich queue: parse_failed → optional LLM → reinject (async, off critical path)."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta

from garimpo.enrich.providers.base import ExtractedOffer, LLMProvider
from garimpo.models.offer import Offer, Price
from garimpo.store.repo import messages as messages_repo


def enqueue(conn: sqlite3.Connection, raw_id: int) -> None:
    now = datetime.now(UTC).replace(tzinfo=None).isoformat()
    conn.execute(
        """
        INSERT OR IGNORE INTO enrich_queue (raw_id, attempts, enqueued_at, next_try_at)
        VALUES (?, 0, ?, ?)
        """,
        (raw_id, now, now),
    )
    conn.commit()


def list_ready(conn: sqlite3.Connection, *, limit: int = 10) -> list[sqlite3.Row]:
    now = datetime.now(UTC).replace(tzinfo=None).isoformat()
    return list(
        conn.execute(
            """
            SELECT q.id AS queue_id, q.raw_id, q.attempts, r.text
            FROM enrich_queue q
            JOIN raw_messages r ON r.id = q.raw_id
            WHERE q.next_try_at <= ?
            ORDER BY q.next_try_at ASC
            LIMIT ?
            """,
            (now, limit),
        ).fetchall()
    )


def mark_done(conn: sqlite3.Connection, queue_id: int) -> None:
    conn.execute("DELETE FROM enrich_queue WHERE id = ?", (queue_id,))
    conn.commit()


def mark_retry(conn: sqlite3.Connection, queue_id: int, attempts: int, error: str) -> None:
    delay = min(3600, 30 * (2 ** max(0, attempts)))
    next_try = (
        datetime.now(UTC).replace(tzinfo=None) + timedelta(seconds=delay)
    ).isoformat()
    conn.execute(
        """
        UPDATE enrich_queue
        SET attempts = ?, last_error = ?, next_try_at = ?
        WHERE id = ?
        """,
        (attempts, error[:500], next_try, queue_id),
    )
    conn.commit()


async def process_one(
    provider: LLMProvider,
    text: str,
) -> ExtractedOffer | None:
    return await provider.extract(text)


def extracted_to_offer(
    extracted: ExtractedOffer,
    *,
    model_key: str,
    confidence: float,
) -> Offer:
    assert extracted.price is not None
    return Offer(
        model_key=model_key,
        price=Price(amount=extracted.price, method=extracted.price_method),
        brand=extracted.brand,
        store=extracted.store,
        condition=extracted.condition,
        extracted_by="llm",
        confidence=confidence,
    )


def fail_raw(conn: sqlite3.Connection, raw_id: int, reason: str) -> None:
    messages_repo.update_raw_status(
        conn, raw_id, status="llm_failed", fail_reason=reason
    )

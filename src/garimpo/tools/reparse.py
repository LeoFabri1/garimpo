"""Reparse stored raw messages with the current parsers.

For after a parser fix: messages that failed back then become offers and
price history now. Never alerts — these offers are old by definition.

Works on the existing raw row instead of feeding the message back through
Pipeline.process. That path re-inserted the message under a fake tg_msg_id,
lost the source's parser hint, tripped the text-hash dedup against its own
original, and — outside dry-run — sent alerts for weeks-old offers.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

from garimpo.catalog import ModelIndex, load_catalog_for_watch
from garimpo.models.offer import Offer
from garimpo.models.raw import RawMessage
from garimpo.parse.groups import ParserRegistry
from garimpo.score.rules import MIN_CONFIDENCE
from garimpo.settings import Settings
from garimpo.store.db import connect
from garimpo.store.repo import history as history_repo
from garimpo.store.repo import messages as messages_repo
from garimpo.store.repo import offers as offers_repo


@dataclass
class ReparseReport:
    scanned: int = 0
    parsed: list[tuple[int, Offer]] = field(default_factory=list)
    duplicates: int = 0
    backup: Path | None = None


def reparse(
    settings: Settings,
    *,
    status: str = "parse_failed",
    since_days: int = 30,
    dry_run: bool = True,
) -> ReparseReport:
    categories = sorted({r.category for r in settings.watch if getattr(r, "category", None)})
    registry = ParserRegistry(ModelIndex(load_catalog_for_watch(categories)))
    report = ReparseReport()

    conn = connect(settings.storage.path)
    try:
        if not dry_run:
            report.backup = _backup(conn, Path(settings.storage.path))
        since = (datetime.now(UTC).replace(tzinfo=None) - timedelta(days=since_days)).isoformat()
        rows = conn.execute(
            """
            SELECT r.id, r.source_id, r.tg_msg_id, r.text, r.has_media, r.received_at,
                   s.username, s.parser
            FROM raw_messages r JOIN sources s ON s.id = r.source_id
            WHERE r.status = ? AND r.received_at >= ?
            ORDER BY r.received_at ASC, r.id ASC
            """,
            (status, since),
        ).fetchall()

        for r in rows:
            report.scanned += 1
            received_at = datetime.fromisoformat(r["received_at"])
            msg = RawMessage(
                source_id=int(r["source_id"]),
                tg_msg_id=int(r["tg_msg_id"]),
                text=r["text"],
                has_media=bool(r["has_media"]),
                received_at=received_at,
                source_username=r["username"],
                parser_hint=r["parser"],
            )
            offer = registry.parse(msg) if r["text"] else None
            if offer is None:
                continue
            if dry_run:
                report.parsed.append((int(r["id"]), offer))
                continue
            if _store(conn, int(r["id"]), offer, received_at, parser=r["parser"] or "generic"):
                report.parsed.append((int(r["id"]), offer))
            else:
                report.duplicates += 1
    finally:
        conn.close()
    return report


def _store(
    conn: sqlite3.Connection,
    raw_id: int,
    offer: Offer,
    received_at: datetime,
    *,
    parser: str,
) -> bool:
    """Same bookkeeping as Pipeline._process, minus scoring and alerting."""
    ohash = offers_repo.offer_hash(offer.model_key, offer.price.amount, offer.store)
    if offers_repo.recent_offer_hash_exists(conn, ohash, now=received_at):
        messages_repo.update_raw_status(conn, raw_id, status="duplicate", parser_used=parser)
        return False
    offer_id = offers_repo.insert_offer(conn, raw_id=raw_id, offer=offer, created_at=received_at)
    if offer.confidence >= MIN_CONFIDENCE:
        history_repo.insert_history(
            conn,
            model_key=offer.model_key,
            price=float(offer.price.amount),
            observed_at=received_at,
            origin="telegram",
            condition=offer.condition,
            store=offer.store,
            offer_id=offer_id,
        )
    messages_repo.update_raw_status(conn, raw_id, status="parsed", parser_used=parser)
    return True


def _backup(conn: sqlite3.Connection, db_path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = db_path.with_name(f"{db_path.name}.pre-reparse-{stamp}")
    dest = sqlite3.connect(str(target))
    try:
        conn.backup(dest)
    finally:
        dest.close()
    return target

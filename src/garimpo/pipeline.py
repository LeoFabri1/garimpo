"""Offline pipeline: message → parse → store → score → channel."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from garimpo.alert.dispatcher import Dispatcher
from garimpo.catalog import ModelIndex, load_gpu_catalog, load_stores
from garimpo.models.alert import Level, ScoredOffer
from garimpo.models.raw import RawMessage
from garimpo.parse.generic import GenericParser
from garimpo.parse.text import normalize_for_hash
from garimpo.parse.triage import passes_triage
from garimpo.score import WatchRule, score_offer
from garimpo.settings import Settings, WatchRuleConfig
from garimpo.store.db import connect
from garimpo.store.repo import alerts as alerts_repo
from garimpo.store.repo import history as history_repo
from garimpo.store.repo import messages as messages_repo
from garimpo.store.repo import offers as offers_repo


@dataclass
class PipelineResult:
    status: str
    raw_id: int | None = None
    offer_id: int | None = None
    scored: ScoredOffer | None = None


_PERF_TIER = re.compile(r">=\s*([\d.]+)")


class Pipeline:
    def __init__(
        self,
        settings: Settings,
        *,
        channel: object | None = None,
        dry_run: bool = False,
        client: object | None = None,
    ) -> None:
        self.settings = settings
        self.dry_run = dry_run
        if channel is not None:
            self.channel = channel  # type: ignore[assignment]
        else:
            from garimpo.alert.channels.factory import build_channel

            self.channel = build_channel(
                settings,
                client=client,  # type: ignore[arg-type]
                force_console=dry_run or settings.alerts.channel == "console",
            )
        self.catalog = load_gpu_catalog()
        self.index = ModelIndex(self.catalog)
        self.parser = GenericParser(self.index)
        self.stores = load_stores()
        self.conn = connect(settings.storage.path)
        self.rules = [_to_watch_rule(r, self.index) for r in settings.watch]
        self.dispatcher = Dispatcher(
            self.conn,
            self.channel,  # type: ignore[arg-type]
            settings.alerts,
            dry_run=dry_run,
        )

    def close(self) -> None:
        self.conn.close()

    def process(self, msg: RawMessage) -> PipelineResult:
        now = msg.received_at
        if now.tzinfo is not None:
            now_naive = now.astimezone(UTC).replace(tzinfo=None)
        else:
            now_naive = now

        text = msg.text or ""
        text_hash = hashlib.sha1(normalize_for_hash(text).encode("utf-8")).hexdigest()

        source_id = messages_repo.ensure_source(
            self.conn,
            tg_id=msg.source_id if msg.source_id else 1,
            username=msg.source_username,
            parser=msg.parser_hint or "generic",
        )

        existing = messages_repo.get_raw_by_tg(self.conn, source_id, msg.tg_msg_id)
        if existing is not None:
            raw_id, status = existing
            return PipelineResult(status=status, raw_id=raw_id)

        if messages_repo.recent_hash_exists(self.conn, text_hash, now=now_naive):
            raw_id = messages_repo.insert_raw_message(
                self.conn,
                source_id=source_id,
                tg_msg_id=msg.tg_msg_id,
                text=msg.text,
                text_hash=text_hash,
                has_media=msg.has_media,
                received_at=now_naive,
                status="duplicate",
            )
            return PipelineResult(status="duplicate", raw_id=raw_id)

        raw_id = messages_repo.insert_raw_message(
            self.conn,
            source_id=source_id,
            tg_msg_id=msg.tg_msg_id,
            text=msg.text,
            text_hash=text_hash,
            has_media=msg.has_media,
            received_at=now_naive,
            status="received",
        )

        if not text or not passes_triage(text):
            messages_repo.update_raw_status(self.conn, raw_id, status="triaged_out")
            return PipelineResult(status="triaged_out", raw_id=raw_id)

        offer = self.parser.parse(msg)
        if offer is None:
            messages_repo.update_raw_status(
                self.conn,
                raw_id,
                status="parse_failed",
                parser_used="generic",
                fail_reason="parse_failed",
            )
            if self.settings.llm.enabled:
                from garimpo.enrich.queue import enqueue

                enqueue(self.conn, raw_id)
                messages_repo.update_raw_status(
                    self.conn, raw_id, status="llm_pending", parser_used="generic"
                )
            return PipelineResult(status="parse_failed", raw_id=raw_id)

        ohash = offers_repo.offer_hash(offer.model_key, offer.price.amount, offer.store)
        if offers_repo.recent_offer_hash_exists(self.conn, ohash, now=now_naive):
            messages_repo.update_raw_status(
                self.conn, raw_id, status="duplicate", parser_used="generic"
            )
            return PipelineResult(status="duplicate", raw_id=raw_id)

        offer_id = offers_repo.insert_offer(
            self.conn, raw_id=raw_id, offer=offer, created_at=now_naive
        )
        history_repo.insert_history(
            self.conn,
            model_key=offer.model_key,
            price=float(offer.price.amount),
            observed_at=now_naive,
            origin="telegram",
            condition=offer.condition,
            store=offer.store,
            offer_id=offer_id,
        )
        messages_repo.update_raw_status(
            self.conn, raw_id, status="parsed", parser_used="generic"
        )

        product = self.catalog.products.get(offer.model_key)
        if product is None:
            return PipelineResult(status="parsed", raw_id=raw_id, offer_id=offer_id)

        history = history_repo.load_history(self.conn, offer.model_key)
        # Exclude the point we just inserted from percentile bias? Keep it — it's real.
        store_trust = float(self.stores.get(offer.store or "", {}).get("trust", 1.0))

        matched_rule = _match_rule(offer.model_key, product.perf, self.rules, offer.store)
        if matched_rule is None:
            return PipelineResult(status="parsed", raw_id=raw_id, offer_id=offer_id)

        scored = score_offer(
            offer,
            product=product,
            history=history,
            rule=matched_rule,
            now=now_naive,
            store_trust=store_trust,
            min_samples=self.settings.scoring.min_samples,
        )

        if scored.level == Level.IGNORE:
            return PipelineResult(
                status="parsed", raw_id=raw_id, offer_id=offer_id, scored=scored
            )

        dispatched = self.dispatcher.dispatch(
            scored, offer_id=offer_id, now=now_naive
        )
        status = "alerted" if dispatched.status in {"sent", "dry_run"} else dispatched.status
        return PipelineResult(
            status=status, raw_id=raw_id, offer_id=offer_id, scored=scored
        )


def _to_watch_rule(cfg: WatchRuleConfig, index: ModelIndex) -> WatchRule:
    model_keys: frozenset[str] | None = None
    if cfg.models:
        resolved: set[str] = set()
        for name in cfg.models:
            hit = index.resolve(name)
            if hit:
                resolved.add(hit.model_key)
            else:
                # allow raw keys
                resolved.add(name.lower().replace(" ", "_"))
        model_keys = frozenset(resolved)

    min_perf: float | None = None
    if cfg.perf_tier:
        m = _PERF_TIER.search(cfg.perf_tier)
        if m:
            min_perf = float(m.group(1))

    return WatchRule(
        name=cfg.name or "default",
        max_price=cfg.max_price,
        models=model_keys,
        min_perf=min_perf,
        max_price_per_perf=cfg.max_price_per_perf,
    )


def _match_rule(
    model_key: str,
    perf: float,
    rules: list[WatchRule],
    store: str | None,
) -> WatchRule | None:
    _ = store  # stores_exclude wired when alert dispatcher lands
    for rule in rules:
        if rule.models is not None:
            if model_key not in rule.models:
                continue
        elif rule.min_perf is not None and perf < rule.min_perf:
            continue
        return rule
    return None


def process_texts(
    settings: Settings,
    texts: list[str],
    *,
    dry_run: bool = True,
) -> list[PipelineResult]:
    pipe = Pipeline(settings, dry_run=dry_run)
    results: list[PipelineResult] = []
    # Unique ids per invocation so re-running dry-run does not collide on UNIQUE
    base_id = int(datetime.now(UTC).timestamp() * 1000)
    try:
        for i, text in enumerate(texts):
            msg = RawMessage(
                source_id=1,
                tg_msg_id=base_id + i,
                text=text,
                has_media=False,
                received_at=datetime.now(UTC),
                source_username="dry-run",
            )
            results.append(pipe.process(msg))
    finally:
        pipe.close()
    return results


def stats_snapshot(settings: Settings) -> dict[str, Any]:
    conn = connect(settings.storage.path)
    try:
        return {
            "user_version": conn.execute("PRAGMA user_version").fetchone()[0],
            "raw_by_status": messages_repo.count_by_status(conn),
            "price_history": history_repo.count_history(conn),
            "alerts_by_level": alerts_repo.count_alerts(conn),
        }
    finally:
        conn.close()

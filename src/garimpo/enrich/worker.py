"""Async enricher: drain parse_failed queue via LLM, reinject offers."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal

import structlog

from garimpo.enrich import queue as enrich_queue
from garimpo.enrich.providers.base import LLMProvider
from garimpo.enrich.providers.factory import build_llm_provider
from garimpo.models.offer import Coupon, Offer, Price
from garimpo.pipeline import Pipeline
from garimpo.store.repo import history as history_repo
from garimpo.store.repo import messages as messages_repo
from garimpo.store.repo import offers as offers_repo

log = structlog.get_logger(__name__)


async def enricher_loop(pipeline: Pipeline, stop: asyncio.Event) -> None:
    provider = build_llm_provider(pipeline.settings)
    if provider is None:
        log.info("enricher_disabled")
        return

    max_attempts = pipeline.settings.llm.max_attempts
    while not stop.is_set():
        try:
            await _drain_once(pipeline, provider, max_attempts=max_attempts)
        except Exception as exc:  # noqa: BLE001 — never kill daemon
            log.warning("enricher_tick_failed", error=str(exc))
        try:
            await asyncio.wait_for(stop.wait(), timeout=15)
        except TimeoutError:
            continue


async def _drain_once(
    pipeline: Pipeline,
    provider: LLMProvider,
    *,
    max_attempts: int,
) -> None:
    ready = enrich_queue.list_ready(pipeline.conn, limit=5)
    for row in ready:
        queue_id = int(row["queue_id"])
        raw_id = int(row["raw_id"])
        attempts = int(row["attempts"]) + 1
        text = row["text"] or ""
        if attempts > max_attempts:
            enrich_queue.mark_done(pipeline.conn, queue_id)
            enrich_queue.fail_raw(pipeline.conn, raw_id, "max_attempts")
            continue
        try:
            extracted = await provider.extract(text)
        except Exception as exc:  # noqa: BLE001
            enrich_queue.mark_retry(pipeline.conn, queue_id, attempts, str(exc))
            continue

        if extracted is None:
            enrich_queue.mark_done(pipeline.conn, queue_id)
            enrich_queue.fail_raw(pipeline.conn, raw_id, "llm_no_offer")
            continue

        conf = {"high": 0.9, "medium": 0.75, "low": 0.5}[extracted.confidence]
        resolved = pipeline.index.resolve(extracted.model_raw or "")
        if resolved is None:
            enrich_queue.mark_done(pipeline.conn, queue_id)
            enrich_queue.fail_raw(pipeline.conn, raw_id, "model_not_found")
            continue

        offer = Offer(
            model_key=resolved.model_key,
            price=Price(
                amount=extracted.price or Decimal("0"),
                method=extracted.price_method,
            ),
            brand=extracted.brand,
            store=extracted.store,
            condition=extracted.condition,
            coupon=Coupon(code=extracted.coupon) if extracted.coupon else None,
            extracted_by="llm",
            confidence=min(conf, resolved.confidence),
        )
        if offer.price.amount <= 0:
            enrich_queue.mark_done(pipeline.conn, queue_id)
            enrich_queue.fail_raw(pipeline.conn, raw_id, "no_price")
            continue

        now = datetime.now(UTC).replace(tzinfo=None)
        offer_id = offers_repo.insert_offer(
            pipeline.conn, raw_id=raw_id, offer=offer, created_at=now
        )
        history_repo.insert_history(
            pipeline.conn,
            model_key=offer.model_key,
            price=float(offer.price.amount),
            observed_at=now,
            origin="telegram",
            condition=offer.condition,
            store=offer.store,
            offer_id=offer_id,
        )
        messages_repo.update_raw_status(
            pipeline.conn, raw_id, status="parsed", parser_used="llm"
        )
        enrich_queue.mark_done(pipeline.conn, queue_id)

        # Score + alert via existing pipeline path pieces
        product = pipeline.catalog.products.get(offer.model_key)
        if product is None:
            continue
        from garimpo.models.alert import Level
        from garimpo.score import score_offer

        history = history_repo.load_history(pipeline.conn, offer.model_key)
        store_trust = float(
            pipeline.stores.get(offer.store or "", {}).get("trust", 1.0)
        )
        matched = None
        for rule in pipeline.rules:
            if rule.models is None or offer.model_key in rule.models:
                matched = rule
                break
        if matched is None:
            continue
        scored = score_offer(
            offer,
            product=product,
            history=history,
            rule=matched,
            now=now,
            store_trust=store_trust,
            min_samples=pipeline.settings.scoring.min_samples,
        )
        if scored.level != Level.IGNORE:
            pipeline.dispatcher.dispatch(scored, offer_id=offer_id, now=now)
        log.info(
            "enricher_parsed",
            raw_id=raw_id,
            model=offer.model_key,
            price=float(offer.price.amount),
            level=scored.level.value,
        )

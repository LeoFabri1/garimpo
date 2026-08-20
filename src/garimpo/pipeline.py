"""Offline pipeline: message → parse → store → score → channel."""

from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import structlog

from garimpo.alert.dispatcher import Dispatcher
from garimpo.catalog import ModelIndex, load_catalog_for_watch, load_stores
from garimpo.models.alert import Level, ScoredOffer
from garimpo.models.raw import RawMessage
from garimpo.parse.groups import ParserRegistry
from garimpo.parse.text import normalize_for_hash
from garimpo.parse.triage import passes_triage
from garimpo.score import match_rule, score_offer, watch_rules_from_settings
from garimpo.score.rules import MIN_CONFIDENCE
from garimpo.settings import Settings
from garimpo.store.db import connect
from garimpo.store.repo import alerts as alerts_repo
from garimpo.store.repo import history as history_repo
from garimpo.store.repo import messages as messages_repo
from garimpo.store.repo import offers as offers_repo
from garimpo.store.retention import purge_raw_noise

if TYPE_CHECKING:
    from garimpo.alert.channels.base import Channel
    from garimpo.ingest.base import MTProtoClient

log = structlog.get_logger(__name__)

# Routine noise: most traffic in a deals group is not an offer at all. Logging
# it at INFO would bury the decisions that matter.
_QUIET_STATUSES = frozenset({"triaged_out", "duplicate", "received"})


def _log_outcome(msg: RawMessage, result: PipelineResult) -> None:
    """One line per message, so `garimpo run` shows it is alive and why it
    decided what it decided."""
    fields: dict[str, Any] = {
        "status": result.status,
        "source": msg.source_username or msg.source_id,
        "msg_id": msg.tg_msg_id,
    }
    if result.scored is not None:
        offer = result.scored.offer
        fields["model"] = offer.model_key
        fields["price"] = float(offer.price.amount)
        fields["level"] = result.scored.level.value
        if result.scored.percentile is not None:
            fields["pct"] = round(result.scored.percentile, 3)
        fields["n"] = result.scored.n_samples
    elif result.status == "parse_failed":
        # Without the text there is no way to tell which parser to fix.
        fields["text"] = (msg.text or "")[:120]

    if result.status in _QUIET_STATUSES:
        log.debug("message", **fields)
    else:
        log.info("message", **fields)


@dataclass
class PipelineResult:
    status: str
    raw_id: int | None = None
    offer_id: int | None = None
    scored: ScoredOffer | None = None


class Pipeline:
    def __init__(
        self,
        settings: Settings,
        *,
        channel: Channel | None = None,
        dry_run: bool = False,
        client: MTProtoClient | None = None,
    ) -> None:
        self.settings = settings
        self.dry_run = dry_run
        if channel is not None:
            self.channel = channel
        else:
            from garimpo.alert.channels.factory import build_channel

            self.channel = build_channel(
                settings,
                client=client,
                force_console=dry_run or settings.alerts.channel == "console",
            )
        categories = sorted({r.category for r in settings.watch if getattr(r, "category", None)})
        self.catalog = load_catalog_for_watch(categories)
        self.index = ModelIndex(self.catalog)
        self.parsers = ParserRegistry(self.index)
        self.stores = load_stores()
        # Um dry-run não pode sujar o histórico real. Antes, `run --dry-run -m`
        # gravava a oferta de exemplo do README no price_history do usuário —
        # um preço fictício que ficava lá para sempre, contaminando o baseline
        # logo na primeira vez que alguém testa o projeto. Banco efêmero
        # preserva todo o comportamento do pipeline sem persistir nada.
        self.conn = connect(":memory:" if dry_run else settings.storage.path)
        self.rules = watch_rules_from_settings(settings, self.index)
        self.dispatcher = Dispatcher(
            self.conn,
            self.channel,
            settings.alerts,
            dry_run=dry_run,
        )

    def close(self) -> None:
        self.conn.close()

    def purge_expired(self, *, now: datetime | None = None) -> int:
        """Drop triaged_out/duplicate raw rows past storage.retention_raw_days."""
        return purge_raw_noise(
            self.conn,
            retention_days=self.settings.storage.retention_raw_days,
            now=now,
        )

    def process(self, msg: RawMessage, *, alert: bool = True) -> PipelineResult:
        """Ingest one message. With ``alert=False`` the offer is stored and
        scored but no alert is sent — used for stale backlog on first run."""
        result = self._process(msg, alert=alert)
        _log_outcome(msg, result)
        return result

    def _process(self, msg: RawMessage, *, alert: bool = True) -> PipelineResult:
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

        offer = self.parsers.parse(msg)
        if offer is None:
            parser_name = msg.parser_hint or "generic"
            messages_repo.update_raw_status(
                self.conn,
                raw_id,
                status="parse_failed",
                parser_used=parser_name,
                fail_reason="parse_failed",
            )
            if self.settings.llm.enabled:
                from garimpo.enrich.queue import enqueue

                enqueue(self.conn, raw_id)
                messages_repo.update_raw_status(
                    self.conn, raw_id, status="llm_pending", parser_used=parser_name
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
        # A low-confidence offer never alerts (score/rules.py), but it used to
        # reach the baseline anyway — that is how mis-parsed prices poisoned the
        # very statistic they were being judged against. Store the offer, not
        # the observation.
        if offer.confidence >= MIN_CONFIDENCE:
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
            self.conn,
            raw_id,
            status="parsed",
            parser_used=msg.parser_hint or "generic",
        )

        product = self.catalog.products.get(offer.model_key)
        if product is None:
            return PipelineResult(status="parsed", raw_id=raw_id, offer_id=offer_id)

        history = history_repo.load_history(self.conn, offer.model_key)
        # Exclude the point we just inserted from percentile bias? Keep it — it's real.
        store_trust = float(self.stores.get(offer.store or "", {}).get("trust", 1.0))

        matched_rule = match_rule(offer.model_key, product.perf, self.rules, offer.store)
        if matched_rule is None:
            return PipelineResult(status="parsed", raw_id=raw_id, offer_id=offer_id)

        scoring = self.settings.scoring
        scored = score_offer(
            offer,
            product=product,
            history=history,
            rule=matched_rule,
            now=now_naive,
            store_trust=store_trust,
            min_samples=scoring.min_samples,
            window_days=scoring.window_days,
            half_life_days=scoring.half_life_days,
        )

        if scored.level == Level.IGNORE:
            return PipelineResult(status="parsed", raw_id=raw_id, offer_id=offer_id, scored=scored)

        if not alert:
            alerts_repo.insert_alert(
                self.conn,
                offer_id=offer_id,
                scored=scored,
                channel=self.channel.name,
                status="suppressed",
                suppressed_by="stale",
                sent_at=now_naive,
            )
            return PipelineResult(
                status="stale_no_alert",
                raw_id=raw_id,
                offer_id=offer_id,
                scored=scored,
            )

        dispatched = self.dispatcher.dispatch(scored, offer_id=offer_id, now=now_naive)
        status = "alerted" if dispatched.status in {"sent", "dry_run"} else dispatched.status
        return PipelineResult(status=status, raw_id=raw_id, offer_id=offer_id, scored=scored)


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


def _baseline_readiness(
    conn: sqlite3.Connection, settings: Settings
) -> dict[str, Any]:
    """Os modelos vigiados já têm amostra para o score valer?

    Abaixo de `scoring.min_samples`, score/rules.py cai num atalho que é só
    filtro de preço máximo: o usuário recebe alertas e acredita que são
    estatísticos. Sem isto aqui, essa diferença é invisível.
    """
    from garimpo.catalog import ModelIndex, load_catalog_for_watch

    categorias = sorted({r.category for r in settings.watch if getattr(r, "category", None)})
    index = ModelIndex(load_catalog_for_watch(categorias))
    vigiados: set[str] = set()
    for rule in watch_rules_from_settings(settings, index):
        if rule.models:
            vigiados |= set(rule.models)

    cutoff = (
        datetime.now(UTC).replace(tzinfo=None)
        - timedelta(days=settings.scoring.window_days)
    ).isoformat()
    contagem = {
        str(r["model_key"]): int(r["n"])
        for r in conn.execute(
            """
            SELECT model_key, COUNT(*) AS n FROM price_history
            WHERE excluded = 0 AND observed_at >= ?
            GROUP BY model_key
            """,
            (cutoff,),
        )
    }

    minimo = settings.scoring.min_samples
    por_modelo = {m: contagem.get(m, 0) for m in sorted(vigiados)}
    sem_baseline = sorted(m for m, n in por_modelo.items() if n < minimo)
    return {
        "min_samples": minimo,
        "window_days": settings.scoring.window_days,
        "watched": por_modelo,
        "with_baseline": sorted(m for m, n in por_modelo.items() if n >= minimo),
        "without_baseline": sem_baseline,
        "warning": (
            f"{len(sem_baseline)} modelo(s) vigiado(s) abaixo de min_samples="
            f"{minimo}: alertas deles NÃO são estatísticos, saem do filtro de "
            "preço máximo"
        )
        if sem_baseline
        else None,
    }


def stats_snapshot(settings: Settings) -> dict[str, Any]:
    conn = connect(settings.storage.path)
    try:
        por_status = messages_repo.count_by_status(conn)
        parsed = por_status.get("parsed", 0)
        falhou = por_status.get("parse_failed", 0)
        tentadas = parsed + falhou
        return {
            "user_version": conn.execute("PRAGMA user_version").fetchone()[0],
            "raw_by_status": por_status,
            # Quanto do que chegou ao parser ele entendeu. Cai quando o canal
            # muda de formato ou quando o catálogo não cobre o que ele posta.
            "parse_rate": round(parsed / tentadas, 3) if tentadas else None,
            "price_history": history_repo.count_history(conn),
            "alerts_by_level": alerts_repo.count_alerts(conn),
            "baseline": _baseline_readiness(conn, settings),
        }
    finally:
        conn.close()

"""Enricher: parse_failed → mock LLM → offer stored."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from garimpo.enrich import queue as enrich_queue
from garimpo.enrich.providers.base import ExtractedOffer
from garimpo.enrich.worker import _drain_once
from garimpo.models.raw import RawMessage
from garimpo.pipeline import Pipeline
from garimpo.settings import load_settings


class _MockLLM:
    async def extract(self, text: str) -> ExtractedOffer | None:
        return ExtractedOffer(
            is_gpu=True,
            model_raw="RTX 5070 Ti",
            brand="ASUS",
            price=Decimal("5799"),
            price_method="pix",
            store="kabum",
            confidence="high",
        )


@pytest.mark.asyncio
async def test_enricher_reinjects_after_parse_failure(tmp_path: Path) -> None:
    settings = load_settings(Path("config/quickstart.yaml"))
    settings.storage.path = str(tmp_path / "garimpo.db")
    settings.alerts.channel = "console"
    settings.llm.enabled = True

    pipe = Pipeline(settings, dry_run=True)
    try:
        # No price → regex parse_failed; enricher should recover via mock LLM.
        msg = RawMessage(
            source_id=1,
            tg_msg_id=77,
            text="RTX 5070 Ti ASUS Dual Kabum promoção",
            has_media=False,
            received_at=datetime.now(UTC),
            parser_hint="generic",
        )
        result = pipe.process(msg)
        assert result.status == "parse_failed"
        assert result.raw_id is not None

        enrich_queue.enqueue(pipe.conn, result.raw_id)
        await _drain_once(pipe, _MockLLM(), max_attempts=3)

        row = pipe.conn.execute(
            "SELECT model_key, price FROM offers WHERE raw_id = ?",
            (result.raw_id,),
        ).fetchone()
        assert row is not None
        assert row["model_key"] == "rtx_5070_ti"
        assert float(row["price"]) == 5799.0

        status = pipe.conn.execute(
            "SELECT status, parser_used FROM raw_messages WHERE id = ?",
            (result.raw_id,),
        ).fetchone()
        assert status["status"] == "parsed"
        assert status["parser_used"] == "llm"
    finally:
        pipe.close()

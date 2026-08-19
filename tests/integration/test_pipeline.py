"""End-to-end offline pipeline (no network)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from garimpo.models.raw import RawMessage
from garimpo.pipeline import Pipeline
from garimpo.settings import load_settings
from garimpo.tools.backfill import backfill_csv


def test_pipeline_parses_and_stores(tmp_path: Path) -> None:
    settings = load_settings(Path("config/quickstart.yaml"))
    settings.storage.path = str(tmp_path / "garimpo.db")
    # Force console channel for dry path
    settings.alerts.channel = "console"

    pipe = Pipeline(settings, dry_run=True)
    try:
        msg = RawMessage(
            source_id=1,
            tg_msg_id=42,
            text="RTX 5070 Ti ASUS — R$ 5.799 no PIX Kabum",
            has_media=False,
            received_at=datetime.now(UTC),
            source_username="test",
        )
        result = pipe.process(msg)
        assert result.status in {"parsed", "alerted"}
        assert result.offer_id is not None

        # duplicate text hash within window
        dup = pipe.process(
            RawMessage(
                source_id=1,
                tg_msg_id=43,
                text="RTX 5070 Ti ASUS — R$ 5.799 no PIX Kabum",
                has_media=False,
                received_at=datetime.now(UTC),
            )
        )
        assert dup.status == "duplicate"
    finally:
        pipe.close()


def test_same_tg_msg_id_is_idempotent(tmp_path: Path) -> None:
    settings = load_settings(Path("config/quickstart.yaml"))
    settings.storage.path = str(tmp_path / "garimpo.db")
    settings.alerts.channel = "console"

    pipe = Pipeline(settings, dry_run=True)
    try:
        msg = RawMessage(
            source_id=1,
            tg_msg_id=99,
            text="RTX 5070 Ti ASUS — R$ 5.799 no PIX Kabum",
            has_media=False,
            received_at=datetime.now(UTC),
            source_username="test",
        )
        first = pipe.process(msg)
        second = pipe.process(msg)
        assert first.raw_id == second.raw_id
        assert second.status in {"parsed", "alerted", first.status}
    finally:
        pipe.close()


def test_backfill_csv(tmp_path: Path) -> None:
    db = tmp_path / "g.db"
    csv_path = tmp_path / "prices.csv"
    csv_path.write_text(
        "model_key,price,store,observed_at\n"
        "rtx_5070_ti,6200,kabum,2026-01-01\n"
        "rtx_5070_ti,6100,kabum,2026-01-15\n"
        "rtx_5070_ti,6000,terabyte,2026-02-01\n",
        encoding="utf-8",
    )
    n = backfill_csv(db, csv_path)
    assert n == 3

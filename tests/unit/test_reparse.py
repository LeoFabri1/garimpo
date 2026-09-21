"""reparse --apply turns old parse failures into offers, never alerts."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from garimpo.settings import Settings
from garimpo.store.db import connect
from garimpo.store.repo import messages as messages_repo
from garimpo.tools.reparse import reparse

TEXT = (
    "Placa de Vídeo NVIDIA GeForce MSI RTX5070TI 16GB GDDR7 SHADOW 3X\n\n"
    "💵6,991\n\nLink\nhttps://loja.example.com/produto"
)


def _settings(tmp_path: Path) -> Settings:
    return Settings.model_validate(
        {
            "storage": {"path": str(tmp_path / "t.db")},
            "watch": [
                {"name": "gpu", "category": "gpu", "models": ["RTX 5070 Ti"], "max_price": 7000}
            ],
            "alerts": {"channel": "console"},
        }
    )


def _seed(settings: Settings, text: str = TEXT) -> int:
    conn = connect(settings.storage.path)
    sid = messages_repo.ensure_source(conn, tg_id=1, username="canal")
    rid = messages_repo.insert_raw_message(
        conn,
        source_id=sid,
        tg_msg_id=42,
        text=text,
        text_hash="h",
        has_media=False,
        received_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(days=3),
        status="parse_failed",
    )
    conn.close()
    return rid


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _seed(settings)
    report = reparse(settings, dry_run=True)
    assert len(report.parsed) == 1
    conn = connect(settings.storage.path)
    assert conn.execute("SELECT COUNT(*) FROM offers").fetchone()[0] == 0
    assert report.backup is None


def test_apply_stores_on_the_original_row_without_alerting(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    rid = _seed(settings)
    report = reparse(settings, dry_run=False)
    assert report.backup is not None and report.backup.exists()
    conn = connect(settings.storage.path)
    offer = conn.execute("SELECT raw_id, model_key, price, url FROM offers").fetchone()
    assert (offer["raw_id"], offer["model_key"], offer["price"]) == (rid, "rtx_5070_ti", 6991.0)
    assert offer["url"] == "https://loja.example.com/produto"
    assert conn.execute("SELECT COUNT(*) FROM price_history").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM raw_messages").fetchone()[0] == 1
    assert conn.execute("SELECT status FROM raw_messages").fetchone()[0] == "parsed"
    assert conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0] == 0
    # Idempotent: nothing left in parse_failed.
    assert reparse(settings, dry_run=False).parsed == []

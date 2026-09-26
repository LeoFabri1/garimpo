"""Wiring do `garimpo backfill` — CSV e --telegram no mesmo comando."""

from __future__ import annotations

import asyncio
import re
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from typer.testing import CliRunner

from garimpo.cli import app
from garimpo.ingest.base import SourceRef
from garimpo.ingest.clients.fake_client import FakeMTProtoClient
from garimpo.models.raw import RawMessage
from garimpo.settings import load_settings
from garimpo.tools.backfill import backfill_telegram

runner = CliRunner()

# Typer forces Rich colours when GITHUB_ACTIONS is set, and the escape codes
# land inside the text ("-\x1b[0m\x1b[1;36m-telegram"). Passed locally, failed
# every CI run.
_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def _plain(output: str) -> str:
    return _ANSI.sub("", output)


def test_backfill_without_source_is_rejected() -> None:
    """Sem CSV e sem --telegram não há o que fazer, e o erro precisa dizer isso."""
    result = runner.invoke(app, ["backfill"])
    assert result.exit_code != 0
    assert "--telegram" in _plain(result.output)


def test_backfill_rejects_csv_and_telegram_together(tmp_path: Path) -> None:
    csv = tmp_path / "h.csv"
    csv.write_text("model_key,price,observed_at\nrtx_5060,2000,2026-08-01\n")
    result = runner.invoke(app, ["backfill", str(csv), "--telegram"])
    assert result.exit_code != 0


def test_backfill_csv_still_works(tmp_path: Path) -> None:
    """O modo CSV é anterior ao --telegram e não pode ter regredido."""
    csv = tmp_path / "h.csv"
    csv.write_text(
        "model_key,price,store,observed_at\n"
        "rtx_5060,1999.00,kabum,2026-08-01T10:00:00\n"
    )
    cfg = tmp_path / "c.yaml"
    cfg.write_text(
        "watch:\n  - name: g\n    category: gpu\n    models: ['RTX 5060']\n"
        f"    max_price: 5000\nstorage:\n  path: {tmp_path / 'db.sqlite'}\n"
    )
    result = runner.invoke(app, ["backfill", str(csv), "-c", str(cfg)])
    assert result.exit_code == 0, result.output
    assert "inserted 1" in result.output


# --- `--days` precisa rebobinar o ponteiro, não só semear fonte virgem ------


def _settings(tmp_path: Path):  # type: ignore[no-untyped-def]
    cfg = tmp_path / "c.yaml"
    cfg.write_text(
        "sources:\n  - '@loja'\n"
        "watch:\n  - name: g\n    category: gpu\n    models: ['RTX 5060']\n"
        f"    max_price: 5000\nstorage:\n  path: {tmp_path / 'db.sqlite'}\n"
    )
    return load_settings(cfg)


def _msgs(n: int) -> list[RawMessage]:
    base = datetime.now(UTC) - timedelta(days=40)
    return [
        RawMessage(
            source_id=0,
            tg_msg_id=i,
            text=f"Placa de Video RTX 5060 8GB R$ {2000 + i}",
            has_media=False,
            received_at=base + timedelta(days=i),
            source_username="loja",
        )
        for i in range(1, n + 1)
    ]


def _run(tmp_path: Path, pointer: int, at_days: int) -> tuple[int, int]:
    """Roda o backfill com o ponteiro já em `pointer`; devolve (msgs, ponteiro)."""
    settings = _settings(tmp_path)
    client = FakeMTProtoClient()
    src = SourceRef(tg_id=None, username="loja", parser="generic")
    resolved = asyncio.run(client.resolve_source(src))
    client.seed(resolved, _msgs(10))
    client.msg_id_at_value = at_days

    import garimpo.ingest.factory as factory

    orig = factory.build_client
    factory.build_client = lambda _s: client  # type: ignore[assignment]

    conn = sqlite3.connect(settings.storage.path)
    try:
        from garimpo.store.db import connect

        c = connect(settings.storage.path)
        from garimpo.store.repo import messages as mrepo

        mrepo.ensure_source(c, tg_id=resolved.tg_id, username="loja", parser="generic")
        c.execute("UPDATE sources SET last_msg_id=? WHERE tg_id=?", (pointer, resolved.tg_id))
        c.commit()
        c.close()
        asyncio.run(backfill_telegram(settings, days=30, progress=lambda _s: None))
    finally:
        factory.build_client = orig  # type: ignore[assignment]
        conn.close()

    c = sqlite3.connect(settings.storage.path)
    n = c.execute("select count(*) from raw_messages").fetchone()[0]
    ptr = c.execute(
        "select last_msg_id from sources where tg_id=?", (resolved.tg_id,)
    ).fetchone()[0]
    c.close()
    return n, ptr


def test_days_rewinds_a_pointer_already_at_the_top(tmp_path: Path) -> None:
    """A fonte já ingerida também precisa obedecer ao `--days`.

    Foi assim que 16 dias de apagão ficaram irrecuperáveis: as 8 fontes tinham
    ponteiro no topo, o backfill só semeava quando last_msg_id era 0, e
    `fetch_since` pede o que é MAIS NOVO que o ponteiro. Resultado: "✓ 0
    mensagens" em todas, que se lê como "o canal não tinha nada".
    """
    n, _ptr = _run(tmp_path, pointer=10, at_days=5)
    assert n == 5, "deveria ter reprocessado da mensagem 6 à 10"


def test_days_never_moves_the_pointer_forward(tmp_path: Path) -> None:
    """Se o ponto de `--days` é mais novo que o ponteiro, o ponteiro fica.

    Avançar puliria as mensagens entre os dois — perder dado calado é pior
    que reprocessar dado que já existe, que o dedup absorve.
    """
    n, _ptr = _run(tmp_path, pointer=3, at_days=8)
    assert n == 7, "deveria ter seguido do 4 ao 10, sem pular para o 8"

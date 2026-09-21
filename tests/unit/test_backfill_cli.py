"""Wiring do `garimpo backfill` — CSV e --telegram no mesmo comando."""

from __future__ import annotations

import re
from pathlib import Path

from typer.testing import CliRunner

from garimpo.cli import app

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

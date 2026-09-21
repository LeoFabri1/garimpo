"""Doctor resolves watch models against every watched category, not GPU only."""

from __future__ import annotations

from pathlib import Path

from garimpo.tools.doctor import run_doctor


def test_ram_model_in_watch_is_found(tmp_path: Path) -> None:
    cfg = tmp_path / "c.yaml"
    cfg.write_text(
        "alerts:\n  channel: console\n"
        "watch:\n"
        "  - name: ram\n    category: ram\n"
        "    models: ['Kingston Fury Beast 16GB DDR5 5600']\n    max_price: 1500\n"
        f"storage:\n  path: {tmp_path / 'g.db'}\n",
        encoding="utf-8",
    )
    results = run_doctor(config=cfg, quick=True)
    check = next(r for r in results if r.label == "modelos do watch no catálogo")
    assert check.ok, check.detail

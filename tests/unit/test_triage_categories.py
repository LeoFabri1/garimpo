"""Category-specific triage only applies to categories the config watches.

RAM terms used to be global: a GPU-only user got every memory deal as a
parse_failed row — logged at INFO, never purged, dragging parse_rate down.
"""

from __future__ import annotations

from pathlib import Path

from garimpo.pipeline import process_texts
from garimpo.settings import Settings

RAM_DEAL = (
    "Memória RAM Kingston Fury Beast, 16GB, 5600MT/s, DDR5, CL36 - KF556C36BBE-16\n"
    "💰 R$ 1.399\nhttps://loja.example.com/produto"
)


def _settings(tmp_path: Path, *categories: str) -> Settings:
    watch = [{"name": c, "category": c, "max_price": 99999} for c in categories]
    return Settings.model_validate(
        {
            "storage": {"path": str(tmp_path / "t.db")},
            "watch": watch,
            "alerts": {"channel": "console"},
        }
    )


def test_gpu_only_config_drops_memory_deals_at_triage(tmp_path: Path) -> None:
    [result] = process_texts(_settings(tmp_path, "gpu"), [RAM_DEAL])
    assert result.status == "triaged_out"


def test_ram_config_parses_memory_deals(tmp_path: Path) -> None:
    [result] = process_texts(_settings(tmp_path, "gpu", "ram"), [RAM_DEAL])
    assert result.status != "triaged_out"
    assert result.scored is not None
    assert result.scored.offer.model_key == "kingston_fury_beast_ddr5_16gb_5600"

"""Settings / config validation."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from garimpo.settings import HealthSettings, Settings, load_settings


def test_load_quickstart() -> None:
    settings = load_settings(Path("config/quickstart.yaml"))
    assert settings.watch
    assert settings.watch[0].max_price == 6000
    assert settings.alerts.channel in {"saved_messages", "console", "bot", "webhook"}


def test_critical_percentile_must_be_stricter() -> None:
    with pytest.raises(ValidationError):
        Settings.model_validate(
            {
                "watch": [{"max_price": 6000, "models": ["RTX 5070 Ti"]}],
                "alerts": {
                    "critical": {"percentile": 0.2},
                    "normal": {"percentile": 0.1},
                },
            }
        )


# --- Seção YAML vazia ------------------------------------------------------
# Comentar o conteúdo de um bloco e deixar a chave é o jeito natural de
# desligar uma seção. Devolvia "Input should be a valid dictionary" sem dizer
# qual seção nem que ela estava vazia.

_BASE = (
    "watch:\n  - name: g\n    category: gpu\n"
    '    models: ["RTX 5060"]\n    max_price: 5000\n'
)


def test_empty_section_falls_back_to_defaults(tmp_path: Path) -> None:
    cfg = tmp_path / "c.yaml"
    cfg.write_text(_BASE + "health:\nstorage:\n  path: /tmp/x.db\n", encoding="utf-8")
    st = load_settings(cfg)
    assert st.health.pulse_minutes == HealthSettings().pulse_minutes
    assert st.storage.path == "/tmp/x.db", "seções vizinhas seguem intactas"


def test_several_empty_sections(tmp_path: Path) -> None:
    cfg = tmp_path / "c.yaml"
    cfg.write_text(_BASE + "health:\nscoring:\nlogging:\n", encoding="utf-8")
    st = load_settings(cfg)
    assert st.scoring.min_samples == 12
    assert st.logging.level == "INFO"


def test_empty_sources_still_means_empty(tmp_path: Path) -> None:
    """`sources:` vazio é "nenhuma fonte", não "traga o default"."""
    cfg = tmp_path / "c.yaml"
    cfg.write_text(_BASE + "sources:\n", encoding="utf-8")
    assert load_settings(cfg).sources == []

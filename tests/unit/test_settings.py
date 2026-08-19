"""Settings / config validation."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from garimpo.settings import Settings, load_settings


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

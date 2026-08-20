"""Doctor must flag an empty `sources:` without failing the run.

The shipped configs now leave sources empty on purpose, so doctor is the only
place that tells you the live run will stop before it does.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from garimpo.tools.doctor import exit_code, run_doctor

_BASE = """
alerts:
  channel: console
watch:
  - name: t
    category: gpu
    max_price: 6000
storage:
  path: {db}
sources: {sources}
"""


def _doctor(tmp_path: Path, sources: str) -> list:
    cfg = tmp_path / "c.yaml"
    cfg.write_text(
        _BASE.format(db=tmp_path / "g.db", sources=sources), encoding="utf-8"
    )
    return run_doctor(config=cfg, quick=True)


def _find(results: list, label: str):
    return next(r for r in results if r.label == label)


def test_empty_sources_warns_but_does_not_fail(tmp_path: Path) -> None:
    results = _doctor(tmp_path, "[]")
    check = _find(results, "sources")
    assert check.warn, "empty sources must be visible as a warning"
    assert check.ok, "it is not a hard failure — --dry-run still works"
    assert "run ao vivo" in (check.detail or ""), "must say what will break"
    assert exit_code(results) == 0


def test_configured_sources_are_listed(tmp_path: Path) -> None:
    results = _doctor(tmp_path, '["@meu_canal"]')
    check = _find(results, "sources")
    assert not check.warn
    assert "@meu_canal" in (check.detail or ""), "show what it will actually read"


def test_disabled_sources_count_as_none(tmp_path: Path) -> None:
    results = _doctor(
        tmp_path, '[{"username": "meu_canal", "enabled": false}]'
    )
    check = _find(results, "sources")
    assert check.warn, "a disabled-only config reads nothing at runtime"


_CHANNEL_CFG = """
alerts:
  channel: {channel}
sources: []
watch:
  - name: t
    category: gpu
    max_price: 6000
storage:
  path: {db}
"""


def _channel_doctor(tmp_path: Path, channel: str) -> list:
    cfg = tmp_path / "c.yaml"
    cfg.write_text(
        _CHANNEL_CFG.format(channel=channel, db=tmp_path / "g.db"), encoding="utf-8"
    )
    return run_doctor(config=cfg, quick=True)


def test_bot_channel_without_env_is_a_hard_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("TG_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TG_CHAT_ID", raising=False)
    # `run_doctor` chama `load_dotenv_if_present()`, que lê `.env` do diretório
    # atual e repovoa o ambiente logo depois do delenv acima. Sem isto, o teste
    # passa ou falha conforme o `.env` de quem roda — quem configurar o canal
    # bot de verdade veria uma falha que não é do código.
    monkeypatch.setattr("garimpo.auth.login.load_dotenv_if_present", lambda: None)
    results = _channel_doctor(tmp_path, "bot")
    check = _find(results, "canal de alerta")
    assert not check.ok, "a channel that cannot deliver must fail, not warn"
    assert "TG_BOT_TOKEN" in (check.detail or "")
    assert exit_code(results) == 1


def test_bot_channel_with_env_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TG_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("TG_CHAT_ID", "456")
    check = _find(_channel_doctor(tmp_path, "bot"), "canal de alerta")
    assert check.ok and not check.warn


def test_bot_channel_works_without_an_explicit_bot_block(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # BotSettings has defaults for both env names, so requiring `bot: {}` in
    # YAML would be a papercut. Webhook already tolerates omission.
    from garimpo.alert.channels.factory import build_channel
    from garimpo.settings import Settings

    monkeypatch.setenv("TG_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("TG_CHAT_ID", "456")
    settings = Settings.model_validate(
        {
            "alerts": {"channel": "bot"},
            "watch": [{"name": "t", "category": "gpu", "max_price": 6000}],
        }
    )
    assert settings.alerts.bot is None
    assert build_channel(settings).name == "bot"


def test_shipped_configs_ship_no_placeholder_channel() -> None:
    # A default pointing at someone else's channel reads as a recommendation
    # and makes users join a group they never chose.
    for name in ("config/quickstart.yaml", "config/config.example.yaml"):
        text = Path(name).read_text(encoding="utf-8")
        active = [
            line
            for line in text.splitlines()
            if "promobit_hardware" in line and not line.strip().startswith("#")
        ]
        assert not active, f"{name} still ships an active placeholder: {active}"

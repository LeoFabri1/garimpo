"""Confirm risk gate for login."""

import unicodedata

import pytest

from garimpo.auth.errors import LoginAborted
from garimpo.auth.warnings import CONFIRM_TOKEN, USERBOT_RISK_BANNER, confirm_userbot_risk

_BANNER_WIDTH = 68


def _visual_width(line: str) -> int:
    return sum(
        2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in line
    )


def test_banner_box_is_aligned() -> None:
    """Every line must fit the box — misaligned banners are unreadable in terminal."""
    for i, line in enumerate(USERBOT_RISK_BANNER.splitlines(), 1):
        assert _visual_width(line) == _BANNER_WIDTH, f"linha {i}: {line!r}"


def _banner_body() -> str:
    """Text inside the box, with line wraps collapsed."""
    parts: list[str] = []
    for line in USERBOT_RISK_BANNER.splitlines():
        if line.startswith("║") and line.endswith("║"):
            parts.append(line[1:-1].strip())
    return " ".join(parts)


def test_banner_states_factual_tos_position() -> None:
    """Lock the factual claims shown at login — not legal conclusions."""
    banner = USERBOT_RISK_BANNER
    body = _banner_body()
    assert "Content Licensing Terms" in body
    assert "telegram.org/tos/content-licensing" in body
    assert "Client, Bot ou Mini App" in body
    assert "não se apresenta como nenhum dos três" in body
    assert "avalie se o seu uso está coberto" in body
    # Must not auto-convict — softened language chosen deliberately.
    assert "FORA DA EXCEÇÃO" not in banner.upper()
    assert "descumpr" not in banner.lower()


def test_banner_lists_mitigations_we_actually_implement() -> None:
    body = _banner_body()
    assert "não lista membros" in body
    assert "não marca" in body and "como lido" in body


def test_confirm_rejects_wrong_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("builtins.input", lambda _: "sim")
    with pytest.raises(LoginAborted):
        confirm_userbot_risk(skip=False)


def test_confirm_accepts_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("builtins.input", lambda _: CONFIRM_TOKEN)
    confirm_userbot_risk(skip=False)


def test_confirm_skip() -> None:
    confirm_userbot_risk(skip=True)

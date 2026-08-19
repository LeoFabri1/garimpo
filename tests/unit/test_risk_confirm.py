"""Confirm risk gate for login."""

import pytest

from garimpo.auth.errors import LoginAborted
from garimpo.auth.warnings import CONFIRM_TOKEN, confirm_userbot_risk


def test_confirm_rejects_wrong_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("builtins.input", lambda _: "sim")
    with pytest.raises(LoginAborted):
        confirm_userbot_risk(skip=False)


def test_confirm_accepts_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("builtins.input", lambda _: CONFIRM_TOKEN)
    confirm_userbot_risk(skip=False)


def test_confirm_skip() -> None:
    confirm_userbot_risk(skip=True)

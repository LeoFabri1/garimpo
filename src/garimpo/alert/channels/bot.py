"""Telegram Bot API channel (v0.1.1) — separate badge/sound via BotFather."""

from __future__ import annotations

import httpx

from garimpo.alert.format import format_alert
from garimpo.models.alert import ScoredOffer


class BotChannel:
    name = "bot"

    def __init__(self, *, token: str, chat_id: str, timeout_s: float = 15.0) -> None:
        self._token = token
        self._chat_id = chat_id
        self._timeout = timeout_s

    def send(self, scored: ScoredOffer, *, silent: bool = False) -> None:
        text = format_alert(scored)
        url = f"https://api.telegram.org/bot{self._token}/sendMessage"
        payload = {
            "chat_id": self._chat_id,
            "text": text,
            "disable_notification": silent,
            "disable_web_page_preview": True,
        }
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            if not data.get("ok"):
                raise RuntimeError(f"Telegram Bot API error: {data}")

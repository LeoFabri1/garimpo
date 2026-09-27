"""Bark siren (iOS): a critical push that rings through silent mode and Focus.

Not an alert channel of its own — the dispatcher fires it next to the main
channel for rules marked `siren: true`, so the Telegram message with the
full text still arrives.
"""

from __future__ import annotations

import httpx

from garimpo.alert.format import format_alert
from garimpo.models.alert import ScoredOffer


class BarkChannel:
    name = "bark"

    def __init__(
        self,
        *,
        key: str,
        server: str = "https://api.day.app",
        timeout_s: float = 10.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._key = key
        self._server = server.rstrip("/")
        self._timeout = timeout_s
        self._transport = transport

    def send(self, scored: ScoredOffer, *, silent: bool = False) -> None:
        offer = scored.offer
        title_lines = format_alert(scored).split("\n", 1)
        payload = {
            "device_key": self._key,
            "title": title_lines[0],
            "body": title_lines[1].strip() if len(title_lines) > 1 else scored.reason,
            # critical ignores the mute switch and Focus; call=1 repeats the
            # ringtone for 30s instead of a single chirp.
            "level": "critical",
            "volume": 10,
            "call": "1",
            "group": "garimpo",
        }
        if offer.url:
            payload["url"] = offer.url
        with httpx.Client(timeout=self._timeout, transport=self._transport) as client:
            resp = client.post(f"{self._server}/push", json=payload)
        # Bark answers errors as HTTP 4xx with the reason in the JSON body
        # ("device token not found"); raise_for_status alone would drop it.
        try:
            data = resp.json()
        except ValueError:
            resp.raise_for_status()
            raise
        if data.get("code") != 200:
            raise RuntimeError(f"Bark error: {data.get('message', data)}")

"""Generic webhook channel (ntfy, Discord, Home Assistant, etc.)."""

from __future__ import annotations

import httpx

from garimpo.alert.format import format_alert
from garimpo.models.alert import ScoredOffer


class WebhookChannel:
    name = "webhook"

    def __init__(
        self,
        *,
        url: str,
        timeout_s: float = 10.0,
        headers: dict[str, str] | None = None,
    ) -> None:
        self._url = url
        self._timeout = timeout_s
        self._headers = headers or {}

    def send(self, scored: ScoredOffer, *, silent: bool = False) -> None:
        text = format_alert(scored)
        # ntfy accepts raw body; Discord wants {"content": ...}
        if "discord.com/api/webhooks" in self._url:
            payload: dict | str = {"content": text[:1900]}
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.post(self._url, json=payload, headers=self._headers)
                resp.raise_for_status()
            return

        headers = {"Title": f"garimpo {scored.level.value}", **self._headers}
        if silent:
            headers["Priority"] = "low"
        else:
            headers["Priority"] = "high"
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.post(self._url, content=text.encode("utf-8"), headers=headers)
            resp.raise_for_status()

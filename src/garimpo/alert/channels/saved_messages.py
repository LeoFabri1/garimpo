"""Saved Messages channel — zero extra config (v0.1)."""

from __future__ import annotations

from garimpo.alert.format import format_alert
from garimpo.ingest.base import MTProtoClient
from garimpo.models.alert import ScoredOffer


class SavedMessagesChannel:
    name = "saved_messages"

    def __init__(self, client: MTProtoClient) -> None:
        self._client = client

    def send(self, scored: ScoredOffer, *, silent: bool = False) -> None:
        import asyncio

        text = format_alert(scored)
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None and loop.is_running():
            # Schedule from sync pipeline called inside async listener
            asyncio.ensure_future(self._client.send_self(text, silent=silent))
        else:
            asyncio.run(self._client.send_self(text, silent=silent))

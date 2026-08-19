"""Build alert channel from settings."""

from __future__ import annotations

from garimpo.alert.channels.base import Channel
from garimpo.alert.channels.console import ConsoleChannel
from garimpo.ingest.base import MTProtoClient
from garimpo.settings import Settings


def build_channel(
    settings: Settings,
    *,
    client: MTProtoClient | None = None,
    force_console: bool = False,
) -> Channel:
    if force_console or settings.alerts.channel == "console":
        return ConsoleChannel()
    if settings.alerts.channel == "saved_messages":
        if client is None:
            raise ValueError(
                "alerts.channel=saved_messages exige cliente Telegram. "
                "Use login + run, ou alerts.channel: console para dry-run."
            )
        from garimpo.alert.channels.saved_messages import SavedMessagesChannel

        return SavedMessagesChannel(client)
    # bot/webhook later
    return ConsoleChannel()

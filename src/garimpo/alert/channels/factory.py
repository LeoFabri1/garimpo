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

    if settings.alerts.channel == "bot":
        bot = settings.alerts.bot
        if bot is None:
            raise ValueError("alerts.bot token_env/chat_id_env obrigatórios")
        token = settings.env(bot.token_env)
        chat_id = settings.env(bot.chat_id_env)
        if not token or not chat_id:
            raise ValueError(
                f"Defina {bot.token_env} e {bot.chat_id_env} no .env para canal bot"
            )
        from garimpo.alert.channels.bot import BotChannel

        return BotChannel(token=token, chat_id=chat_id)

    return ConsoleChannel()

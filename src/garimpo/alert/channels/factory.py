"""Build alert channel from settings."""

from __future__ import annotations

from garimpo.alert.channels.base import Channel
from garimpo.alert.channels.console import ConsoleChannel
from garimpo.ingest.base import MTProtoClient
from garimpo.settings import BotSettings, Settings, WebhookSettings


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
        # Env var names have defaults, so an omitted `bot:` block is fine —
        # same as the webhook branch below.
        bot = settings.alerts.bot or BotSettings()
        token = settings.env(bot.token_env)
        chat_id = settings.env(bot.chat_id_env)
        if not token or not chat_id:
            raise ValueError(
                f"Defina {bot.token_env} e {bot.chat_id_env} no .env para canal bot"
            )
        from garimpo.alert.channels.bot import BotChannel

        return BotChannel(token=token, chat_id=chat_id)

    if settings.alerts.channel == "webhook":
        wh = settings.alerts.webhook or WebhookSettings()
        url = settings.env(wh.url_env)
        if not url:
            raise ValueError(f"Defina {wh.url_env} no .env para canal webhook")
        from garimpo.alert.channels.webhook import WebhookChannel

        return WebhookChannel(url=url)

    return ConsoleChannel()

"""Telethon-backed MTProtoClient (optional extra)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from garimpo.ingest.base import Handler, SourceRef
from garimpo.models.raw import RawMessage


class TelethonUnavailableError(RuntimeError):
    def __init__(self) -> None:
        super().__init__(
            "Telethon não instalado. Rode: uv sync --extra telethon\n"
            "(pin exato telethon==1.44.0)"
        )


def _require_telethon() -> None:
    try:
        import telethon  # noqa: F401
    except ImportError as exc:
        raise TelethonUnavailableError() from exc


class TelethonClient:
    def __init__(
        self,
        *,
        session: str,
        api_id: int,
        api_hash: str,
        device_model: str = "Desktop",
        system_version: str = "Linux 6.8",
        app_version: str = "garimpo 0.0.1",
        session_string: str | None = None,
    ) -> None:
        _require_telethon()
        from telethon import TelegramClient
        from telethon.sessions import StringSession

        session_obj: Any
        if session_string:
            session_obj = StringSession(session_string)
        else:
            session_obj = session

        self._client = TelegramClient(
            session_obj,
            api_id,
            api_hash,
            connection_retries=None,
            retry_delay=5,
            auto_reconnect=True,
            flood_sleep_threshold=60,
            device_model=device_model,
            system_version=system_version,
            app_version=app_version,
        )
        self._handler: Handler | None = None
        self._sources_by_id: dict[int, SourceRef] = {}

    @property
    def raw(self) -> Any:
        """Underlying Telethon client (login / QR flows)."""
        return self._client

    async def start(self) -> None:
        await self._client.connect()
        if not await self._client.is_user_authorized():
            raise RuntimeError(
                "Sessão não autenticada. Rode: uv run garimpo login --qr"
            )

    async def stop(self) -> None:
        await self._client.disconnect()

    def on_new_message(self, sources: list[SourceRef], handler: Handler) -> None:
        """Register handler. Prefer resolving sources first so tg_id is set."""
        from telethon import events

        self._handler = handler
        chat_ids: list[int] = []
        for s in sources:
            if s.tg_id is not None:
                self._sources_by_id[int(s.tg_id)] = s
                chat_ids.append(int(s.tg_id))

        @self._client.on(events.NewMessage(chats=chat_ids or None, incoming=True))
        async def _on_event(event: Any) -> None:
            chat = await event.get_chat()
            chat_id = int(chat.id)
            src = self._sources_by_id.get(chat_id)
            if src is None and chat_ids:
                return
            username = getattr(chat, "username", None)
            text = event.message.message if event.message else None
            msg = RawMessage(
                source_id=chat_id,
                tg_msg_id=int(event.message.id),
                text=text,
                has_media=bool(event.message and event.message.media),
                received_at=datetime.now(UTC),
                source_username=username.lower() if username else (src.username if src else None),
                parser_hint=src.parser if src else "generic",
            )
            if self._handler is not None:
                result = self._handler(msg)
                if result is not None:
                    await result

    async def fetch_since(
        self, source: SourceRef, min_id: int, limit: int
    ) -> list[RawMessage]:
        entity: Any = source.tg_id if source.tg_id is not None else source.username
        if entity is None:
            return []
        out: list[RawMessage] = []
        async for message in self._client.iter_messages(
            entity, min_id=min_id, limit=limit, reverse=True
        ):
            chat = await message.get_chat()
            username = getattr(chat, "username", None)
            date = message.date
            if date.tzinfo is None:
                date = date.replace(tzinfo=UTC)
            out.append(
                RawMessage(
                    source_id=int(getattr(chat, "id", source.tg_id or 0)),
                    tg_msg_id=int(message.id),
                    text=message.message,
                    has_media=bool(message.media),
                    received_at=date,
                    source_username=username.lower() if username else source.username,
                    parser_hint=source.parser,
                )
            )
        return out

    async def send_self(self, text: str, *, silent: bool = False) -> None:
        await self._client.send_message("me", text, silent=silent)

    async def is_authorized(self) -> bool:
        if not self._client.is_connected():
            await self._client.connect()
        return bool(await self._client.is_user_authorized())

    async def resolve_source(self, source: SourceRef) -> SourceRef:
        entity: Any = source.tg_id if source.tg_id is not None else source.username
        if entity is None:
            return source
        ent = await self._client.get_entity(entity)
        username = getattr(ent, "username", None)
        resolved = SourceRef(
            tg_id=int(ent.id),
            username=username,
            parser=source.parser,
        )
        if resolved.tg_id is not None:
            self._sources_by_id[resolved.tg_id] = resolved
        return resolved

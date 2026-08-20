"""PyroTGFork-backed MTProtoClient (optional extra `pyro`)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from garimpo import DEFAULT_APP_VERSION
from garimpo.ingest.base import Handler, SourceRef
from garimpo.models.raw import RawMessage


class PyroUnavailableError(RuntimeError):
    def __init__(self) -> None:
        super().__init__(
            "pyrotgfork não instalado. Rode: uv sync --extra pyro\n"
            "(backend alternativo ao Telethon)"
        )


def _require_pyro() -> None:
    try:
        import pyrogram  # noqa: F401
    except ImportError as exc:
        raise PyroUnavailableError() from exc


def _session_name_and_workdir(session: str) -> tuple[str, str]:
    path = Path(session)
    # Telethon uses "data/session.session"; pyrogram adds ".session" to name.
    name = path.stem if path.suffix == ".session" else path.name
    workdir = str(path.parent) if str(path.parent) not in {"", "."} else "."
    return name, workdir


def message_to_raw(message: Any, source: SourceRef | None) -> RawMessage:
    """Map a pyrogram Message into our RawMessage (pure, testable)."""
    chat = message.chat
    chat_id = int(chat.id) if chat is not None else int(source.tg_id or 0)
    username = getattr(chat, "username", None) if chat is not None else None
    date = message.date or datetime.now(UTC)
    if date.tzinfo is None:
        date = date.replace(tzinfo=UTC)
    text = message.text or message.caption
    return RawMessage(
        source_id=chat_id,
        tg_msg_id=int(message.id),
        text=text,
        has_media=bool(message.media),
        received_at=date,
        source_username=(
            username.lower()
            if username
            else (source.username if source else None)
        ),
        parser_hint=source.parser if source else "generic",
    )


class PyroClient:
    """MTProtoClient using community-maintained pyrotgfork (namespace: pyrogram)."""

    def __init__(
        self,
        *,
        session: str,
        api_id: int,
        api_hash: str,
        device_model: str = "Desktop",
        system_version: str = "Linux 6.8",
        app_version: str = DEFAULT_APP_VERSION,
        session_string: str | None = None,
    ) -> None:
        _require_pyro()
        from pyrogram import Client

        kwargs: dict[str, Any] = {
            "api_id": api_id,
            "api_hash": api_hash,
            "device_model": device_model,
            "system_version": system_version,
            "app_version": app_version,
            "no_updates": False,
        }
        if session_string:
            self._client = Client(
                name="garimpo",
                session_string=session_string,
                in_memory=True,
                **kwargs,
            )
        else:
            name, workdir = _session_name_and_workdir(session)
            self._client = Client(name=name, workdir=workdir, **kwargs)

        self._handler: Handler | None = None
        self._sources_by_id: dict[int, SourceRef] = {}
        self._handler_registered = False

    @property
    def raw(self) -> Any:
        return self._client

    async def start(self) -> None:
        from pyrogram import raw

        is_authorized = await self._client.connect()
        if not is_authorized:
            await self._client.disconnect()
            raise RuntimeError(
                "Sessão não autenticada. Rode: uv run garimpo login --qr "
                "(ou migre a sessão Telethon — ver docs/hosting.md)"
            )
        try:
            await self._client.invoke(raw.functions.updates.GetState())
            self._client.me = await self._client.get_me()
            await self._client.initialize()
        except Exception:
            await self._client.disconnect()
            raise

    async def stop(self) -> None:
        if getattr(self._client, "is_initialized", False):
            await self._client.stop()
        elif getattr(self._client, "is_connected", False):
            await self._client.disconnect()

    def on_new_message(self, sources: list[SourceRef], handler: Handler) -> None:
        from pyrogram import filters
        from pyrogram.handlers import MessageHandler

        self._handler = handler
        chat_ids: list[int] = []
        for s in sources:
            if s.tg_id is not None:
                self._sources_by_id[int(s.tg_id)] = s
                chat_ids.append(int(s.tg_id))

        if self._handler_registered:
            return

        async def _on_message(_client: Any, message: Any) -> None:
            chat = message.chat
            if chat is None:
                return
            chat_id = int(chat.id)
            src = self._sources_by_id.get(chat_id)
            if src is None and chat_ids:
                return
            msg = message_to_raw(message, src)
            if self._handler is not None:
                result = self._handler(msg)
                if result is not None:
                    await result

        chat_filter = filters.chat(chat_ids) if chat_ids else filters.all
        self._client.add_handler(
            MessageHandler(_on_message, chat_filter & filters.incoming)
        )
        self._handler_registered = True

    def is_connected(self) -> bool:
        # pyrogram expõe como atributo, não método; getattr evita quebrar o
        # daemon se a forma mudar entre versões do fork.
        estado = getattr(self._client, "is_connected", False)
        return bool(estado() if callable(estado) else estado)

    async def msg_id_at(self, source: SourceRef, days_ago: int) -> int:
        """Não implementado no backend pyro — o backfill cai para o início do
        canal e avisa. Ver docs/onboarding.md."""
        raise NotImplementedError("msg_id_at: use o backend telethon")

    async def fetch_since(
        self, source: SourceRef, min_id: int, limit: int
    ) -> list[RawMessage]:
        entity: Any = source.tg_id if source.tg_id is not None else source.username
        if entity is None:
            return []
        out: list[RawMessage] = []
        async for message in self._client.get_chat_history(
            entity, min_id=min_id, limit=limit, reverse=True
        ):
            out.append(message_to_raw(message, source))
        return out

    async def send_self(self, text: str, *, silent: bool = False) -> None:
        await self._client.send_message(
            "me", text, disable_notification=silent
        )

    async def is_authorized(self) -> bool:
        if not self._client.is_connected:
            ok = await self._client.connect()
            if not ok:
                return False
        return bool(await self._client.storage.is_user_authorized())

    async def resolve_source(self, source: SourceRef) -> SourceRef:
        entity: Any = source.tg_id if source.tg_id is not None else source.username
        if entity is None:
            return source
        chat = await self._client.get_chat(entity)
        username = getattr(chat, "username", None)
        resolved = SourceRef(
            tg_id=int(chat.id),
            username=username,
            parser=source.parser,
        )
        if resolved.tg_id is not None:
            self._sources_by_id[resolved.tg_id] = resolved
        return resolved

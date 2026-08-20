"""MTProto client Protocol — P8 exit hatch for abandoned libraries."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol

from garimpo.models.raw import RawMessage

Handler = Callable[[RawMessage], Awaitable[None] | None]


@dataclass(frozen=True, slots=True)
class SourceRef:
    """A Telegram source to listen to / fetch from."""

    tg_id: int | None = None
    username: str | None = None
    parser: str = "generic"

    def key(self) -> str:
        if self.username:
            return self.username.lstrip("@").lower()
        if self.tg_id is not None:
            return str(self.tg_id)
        raise ValueError("SourceRef needs tg_id or username")


class MTProtoClient(Protocol):
    async def start(self) -> None: ...

    async def stop(self) -> None: ...

    def on_new_message(self, sources: list[SourceRef], handler: Handler) -> None: ...

    async def fetch_since(
        self, source: SourceRef, min_id: int, limit: int
    ) -> list[RawMessage]: ...

    async def send_self(self, text: str, *, silent: bool = False) -> None: ...

    async def is_authorized(self) -> bool: ...

    async def resolve_source(self, source: SourceRef) -> SourceRef: ...

    def is_connected(self) -> bool:
        """Estado local do socket. NÃO fala com o Telegram.

        O laço de recuperação pós-reconexão consulta isto a cada poucos
        segundos; se custasse uma chamada de API, viraria polling do que
        deveria ser detecção de evento.
        """
        ...

    async def msg_id_at(self, source: SourceRef, days_ago: int) -> int:
        """Id da mensagem publicada há ~`days_ago` dias, ou 0 se não houver.

        Existe para o backfill saber onde começar. Sem isto, `last_msg_id = 0`
        e a ingestão parte do primeiro dia do canal — que num grupo de 2020 é
        preço de placa de vídeo de cinco anos atrás, e o usuário não descobre
        que está lendo lixo até olhar as datas no banco.
        """
        ...

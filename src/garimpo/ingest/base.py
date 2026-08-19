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

"""PyroTGFork backend stub — Protocol-compatible exit hatch (Sprint 8 / v0.4)."""

from __future__ import annotations

from garimpo.ingest.base import Handler, SourceRef
from garimpo.models.raw import RawMessage


class PyroClient:
    """Placeholder until Telethon migration is required (DESIGN §3.3 / §25)."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise NotImplementedError(
            "Backend pyrotgfork ainda não implementado. "
            "Use telegram.backend: telethon. "
            "O Protocol MTProtoClient + contract tests já estão prontos para a troca."
        )

    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    def on_new_message(self, sources: list[SourceRef], handler: Handler) -> None: ...
    async def fetch_since(
        self, source: SourceRef, min_id: int, limit: int
    ) -> list[RawMessage]: ...
    async def send_self(self, text: str, *, silent: bool = False) -> None: ...
    async def is_authorized(self) -> bool: ...
    async def resolve_source(self, source: SourceRef) -> SourceRef: ...

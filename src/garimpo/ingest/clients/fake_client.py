"""In-memory MTProto client for tests (no network)."""

from __future__ import annotations

from garimpo.ingest.base import Handler, SourceRef
from garimpo.models.raw import RawMessage


class FakeMTProtoClient:
    """Contract-compatible fake: inject messages, capture send_self."""

    def __init__(self) -> None:
        self.started = False
        self._handler: Handler | None = None
        self._sources: list[SourceRef] = []
        self.sent: list[tuple[str, bool]] = []
        self._inbox: dict[str, list[RawMessage]] = {}
        self.authorized = True

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.started = False

    def on_new_message(self, sources: list[SourceRef], handler: Handler) -> None:
        self._sources = list(sources)
        self._handler = handler

    async def fetch_since(
        self, source: SourceRef, min_id: int, limit: int
    ) -> list[RawMessage]:
        key = source.key()
        msgs = [m for m in self._inbox.get(key, []) if m.tg_msg_id > min_id]
        msgs.sort(key=lambda m: m.tg_msg_id)
        return msgs[:limit]

    async def send_self(self, text: str, *, silent: bool = False) -> None:
        self.sent.append((text, silent))

    async def is_authorized(self) -> bool:
        return self.authorized

    async def resolve_source(self, source: SourceRef) -> SourceRef:
        if source.tg_id is None and source.username:
            # stable fake id from username
            tg_id = abs(hash(source.username)) % 1_000_000_000
            return SourceRef(tg_id=tg_id, username=source.username, parser=source.parser)
        return source

    # --- test helpers ---

    def seed(self, source: SourceRef, messages: list[RawMessage]) -> None:
        key = source.key()
        self._inbox.setdefault(key, []).extend(messages)

    async def emit(self, msg: RawMessage) -> None:
        if self._handler is None:
            raise RuntimeError("no handler registered")
        result = self._handler(msg)
        if result is not None:
            await result

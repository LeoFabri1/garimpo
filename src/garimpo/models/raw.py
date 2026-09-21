"""Raw Telegram message as seen by the pipeline (pre-parse)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class RawMessage:
    source_id: int
    tg_msg_id: int
    text: str | None
    has_media: bool
    received_at: datetime
    source_username: str | None = None
    parser_hint: str | None = None
    # When Telegram says it was posted. received_at is when we got it; the gap
    # is ingest lag, logged per message as lag_s.
    posted_at: datetime | None = None

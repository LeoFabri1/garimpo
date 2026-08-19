"""Parser protocol."""

from __future__ import annotations

from typing import Protocol

from garimpo.models.offer import Offer
from garimpo.models.raw import RawMessage


class Parser(Protocol):
    name: str

    def can_handle(self, msg: RawMessage) -> bool: ...

    def parse(self, msg: RawMessage) -> Offer | None: ...

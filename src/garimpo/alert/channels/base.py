"""Alert channel protocol."""

from __future__ import annotations

from typing import Protocol

from garimpo.models.alert import ScoredOffer


class Channel(Protocol):
    name: str

    def send(self, scored: ScoredOffer, *, silent: bool = False) -> None: ...

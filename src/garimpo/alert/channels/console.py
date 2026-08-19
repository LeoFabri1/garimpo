"""Console channel — dry-run and local testing."""

from __future__ import annotations

import sys

from garimpo.alert.format import format_alert
from garimpo.models.alert import ScoredOffer


class ConsoleChannel:
    name = "console"

    def __init__(self, stream: object | None = None) -> None:
        self._stream = stream or sys.stdout

    def send(self, scored: ScoredOffer, *, silent: bool = False) -> None:
        text = format_alert(scored)
        if silent:
            text = f"{text}\n  (silent)"
        print(text, file=self._stream)  # noqa: T201

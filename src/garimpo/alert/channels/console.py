"""Console channel — dry-run and local testing."""

from __future__ import annotations

import sys

from garimpo.models.alert import Level, ScoredOffer


class ConsoleChannel:
    name = "console"

    def __init__(self, stream: object | None = None) -> None:
        self._stream = stream or sys.stdout

    def send(self, scored: ScoredOffer, *, silent: bool = False) -> None:
        offer = scored.offer
        badge = "🚨" if scored.level == Level.CRITICAL else "📉"
        lines = [
            f"{badge} [{scored.level.value}] {offer.model_key} — R$ {offer.price.amount}",
            f"  store={offer.store or '?'} method={offer.price.method} "
            f"confidence={offer.confidence:.2f}",
            f"  {scored.reason}",
        ]
        if silent:
            lines.append("  (silent)")
        print("\n".join(lines), file=self._stream)  # noqa: T201

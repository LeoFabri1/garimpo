"""Community telemetry — opt-in, default OFF."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import httpx
import structlog

log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class TelemetryPoint:
    model_key: str
    price: float
    store: str | None
    observed_at: datetime


async def maybe_send(
    points: list[TelemetryPoint],
    *,
    enabled: bool,
    endpoint: str | None,
) -> int:
    """Send anonymized (model_key, price, store, timestamp) only if enabled."""
    if not enabled or not endpoint or not points:
        return 0
    payload = [
        {
            "model_key": p.model_key,
            "price": p.price,
            "store": p.store,
            "timestamp": p.observed_at.astimezone(UTC).isoformat(),
        }
        for p in points
    ]
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(endpoint, json={"points": payload})
        resp.raise_for_status()
    log.info("telemetry_sent", n=len(payload))
    return len(payload)

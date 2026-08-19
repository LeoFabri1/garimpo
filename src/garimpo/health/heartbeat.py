"""Optional heartbeat ping (DESIGN §17.3)."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import structlog

log = structlog.get_logger(__name__)


async def ping(url: str, *, timeout_s: float = 10.0) -> bool:
    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            resp = await client.get(url)
            ok = resp.status_code < 400
            log.info("heartbeat", status=resp.status_code, ok=ok)
            return ok
    except Exception as exc:  # noqa: BLE001
        log.warning("heartbeat_failed", error=str(exc))
        return False


async def heartbeat_loop(
    url: str,
    stop_event: asyncio.Event,
    *,
    interval_minutes: int = 5,
) -> None:
    while not stop_event.is_set():
        await ping(url)
        try:
            await asyncio.wait_for(
                stop_event.wait(), timeout=max(60, interval_minutes * 60)
            )
        except TimeoutError:
            continue


def resolve_heartbeat_url(settings: Any) -> str | None:
    env_name = settings.health.heartbeat_url_env
    if not env_name:
        return None
    return settings.env(env_name)

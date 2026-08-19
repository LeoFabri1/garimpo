"""Listener loop: resolve sources, gap recovery, then live events."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from garimpo.ingest.base import MTProtoClient, SourceRef
from garimpo.ingest.recovery import recover_source
from garimpo.models.raw import RawMessage
from garimpo.pipeline import Pipeline


async def run_once(
    client: MTProtoClient,
    pipeline: Pipeline,
    sources: list[SourceRef],
) -> int:
    """Single pass gap recovery across all sources, then stop."""
    await client.start()
    total = 0
    try:
        resolved: list[SourceRef] = []
        for src in sources:
            resolved.append(await client.resolve_source(src))
        for src in resolved:
            total += await recover_source(client, pipeline, src, alert=True)
    finally:
        await client.stop()
    return total


async def run_daemon(
    client: MTProtoClient,
    pipeline: Pipeline,
    sources: list[SourceRef],
    *,
    stop_event: asyncio.Event | None = None,
) -> None:
    """Connect, recover gaps, then listen until stop_event is set."""
    await client.start()
    resolved: list[SourceRef] = []
    for src in sources:
        resolved.append(await client.resolve_source(src))

    for src in resolved:
        await recover_source(client, pipeline, src, alert=True)

    async def _handle(msg: RawMessage) -> None:
        pipeline.process(msg)
        # advance cursor
        from garimpo.ingest.recovery import set_last_msg_id

        set_last_msg_id(pipeline.conn, msg.source_id, msg.tg_msg_id)

    client.on_new_message(resolved, _handle)

    stop = stop_event or asyncio.Event()
    try:
        await stop.wait()
    finally:
        await client.stop()


def sync_run(coro_factory: Callable[[], Awaitable[object]]) -> object:
    return asyncio.run(coro_factory())

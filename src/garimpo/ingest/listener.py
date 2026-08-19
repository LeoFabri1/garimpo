"""Listener loop: resolve sources, gap recovery, then live events."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime

from garimpo.alert.quiet import in_quiet_hours
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
        from garimpo.ingest.recovery import set_last_msg_id

        set_last_msg_id(pipeline.conn, msg.source_id, msg.tg_msg_id)

    client.on_new_message(resolved, _handle)

    stop = stop_event or asyncio.Event()
    tasks: list[asyncio.Task[None]] = [
        asyncio.create_task(_quiet_flush_loop(pipeline, stop)),
    ]

    if pipeline.settings.llm.enabled:
        from garimpo.enrich.worker import enricher_loop

        tasks.append(asyncio.create_task(enricher_loop(pipeline, stop)))

    from garimpo.health.heartbeat import heartbeat_loop, resolve_heartbeat_url

    hb_url = resolve_heartbeat_url(pipeline.settings)
    if hb_url:
        tasks.append(
            asyncio.create_task(
                heartbeat_loop(
                    hb_url,
                    stop,
                    interval_minutes=pipeline.settings.health.interval_minutes,
                )
            )
        )

    try:
        await stop.wait()
    finally:
        stop.set()
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await client.stop()


async def _quiet_flush_loop(pipeline: Pipeline, stop: asyncio.Event) -> None:
    """When leaving quiet hours, flush deferred normals as one digest."""
    was_quiet = False
    while not stop.is_set():
        now = datetime.now()
        quiet = pipeline.settings.alerts.normal.quiet_hours
        quiet_now = in_quiet_hours(now, quiet)
        if was_quiet and not quiet_now:
            pipeline.dispatcher.flush_deferred(now=now)
        was_quiet = quiet_now
        try:
            await asyncio.wait_for(stop.wait(), timeout=60)
        except TimeoutError:
            continue


def sync_run(coro_factory: Callable[[], Awaitable[object]]) -> object:
    return asyncio.run(coro_factory())

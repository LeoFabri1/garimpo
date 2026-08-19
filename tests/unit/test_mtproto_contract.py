"""Contract tests any MTProtoClient implementation must pass."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from garimpo.ingest.base import SourceRef
from garimpo.ingest.clients.fake_client import FakeMTProtoClient
from garimpo.models.raw import RawMessage


@pytest.fixture
def client() -> FakeMTProtoClient:
    return FakeMTProtoClient()


@pytest.mark.asyncio
async def test_start_stop(client: FakeMTProtoClient) -> None:
    await client.start()
    assert client.started
    await client.stop()
    assert not client.started


@pytest.mark.asyncio
async def test_fetch_since_respects_min_id(client: FakeMTProtoClient) -> None:
    src = SourceRef(username="promobit_hardware", tg_id=123)
    now = datetime.now(UTC)
    client.seed(
        src,
        [
            RawMessage(123, 1, "old", False, now - timedelta(hours=1)),
            RawMessage(123, 5, "new", False, now),
            RawMessage(123, 6, "newer", False, now),
        ],
    )
    await client.start()
    got = await client.fetch_since(src, min_id=1, limit=200)
    assert [m.tg_msg_id for m in got] == [5, 6]


@pytest.mark.asyncio
async def test_send_self(client: FakeMTProtoClient) -> None:
    await client.start()
    await client.send_self("hello", silent=True)
    assert client.sent == [("hello", True)]


@pytest.mark.asyncio
async def test_on_new_message_handler(client: FakeMTProtoClient) -> None:
    src = SourceRef(username="x", tg_id=1)
    seen: list[RawMessage] = []

    async def handler(msg: RawMessage) -> None:
        seen.append(msg)

    client.on_new_message([src], handler)
    await client.start()
    msg = RawMessage(1, 10, "RTX 5070 Ti", False, datetime.now(UTC))
    await client.emit(msg)
    assert len(seen) == 1
    assert seen[0].tg_msg_id == 10


@pytest.mark.asyncio
async def test_resolve_source_assigns_id(client: FakeMTProtoClient) -> None:
    src = SourceRef(username="pechinchou_gpu")
    resolved = await client.resolve_source(src)
    assert resolved.tg_id is not None
    assert resolved.username == "pechinchou_gpu"

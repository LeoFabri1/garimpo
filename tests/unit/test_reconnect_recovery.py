"""Recuperar a lacuna quando a conexão volta — sem virar polling nem inundar.

run_daemon recuperava lacunas só no boot. O Telethon reconecta sozinho, então
o processo sobrevive a uma queda e retoma os eventos dali em diante: as
mensagens do intervalo nunca eram buscadas, em silêncio.
"""

from __future__ import annotations

import asyncio

import pytest

from garimpo.ingest.base import SourceRef
from garimpo.ingest.listener import reconnect_recovery_loop


class _Client:
    """Estados de conexão em sequência, um por sondagem."""

    def __init__(self, estados: list[bool]) -> None:
        self._estados = list(estados)
        self.sondagens = 0
        self.recuperacoes: list[str] = []

    def is_connected(self) -> bool:
        self.sondagens += 1
        return self._estados.pop(0) if self._estados else True


class _Pipeline:
    settings = None


async def _drive(client, sources, *, ticks: int, recover) -> None:
    """Roda o laço por `ticks` sondagens e para."""
    stop = asyncio.Event()

    async def _parar() -> None:
        while client.sondagens < ticks:
            await asyncio.sleep(0)
        stop.set()

    await asyncio.gather(
        reconnect_recovery_loop(
            client, _Pipeline(), sources, stop, interval_s=0.001
        ),
        _parar(),
    )


@pytest.fixture
def sources() -> list[SourceRef]:
    return [SourceRef(tg_id=1, username="a"), SourceRef(tg_id=2, username="b")]


def test_reconnection_triggers_recovery(monkeypatch, sources) -> None:
    chamadas: list[tuple[str, bool]] = []

    async def _fake(client, pipeline, src, *, limit=200, alert=True, now=None):
        chamadas.append((src.username or "", alert))
        return 3

    monkeypatch.setattr("garimpo.ingest.listener.recover_source", _fake)
    client = _Client([True, False, True])
    asyncio.run(_drive(client, sources, ticks=3, recover=_fake))

    assert [c[0] for c in chamadas] == ["a", "b"], "recupera cada fonte uma vez"
    assert all(alert for _, alert in chamadas), (
        "alert=True: uma queda curta deve alertar; quem cala backlog velho é "
        "o ALERT_MAX_AGE dentro de recover_source"
    )


def test_steady_connection_never_recovers_and_never_calls_telegram(
    monkeypatch, sources
) -> None:
    """O critério que separa detecção de evento de polling."""
    chamadas: list[str] = []

    async def _fake(client, pipeline, src, *, limit=200, alert=True, now=None):
        chamadas.append(src.username or "")
        return 0

    monkeypatch.setattr("garimpo.ingest.listener.recover_source", _fake)
    client = _Client([True, True, True, True])
    asyncio.run(_drive(client, sources, ticks=4, recover=_fake))
    assert chamadas == []


def test_recovery_failure_does_not_kill_the_daemon(monkeypatch, sources) -> None:
    tentadas: list[str] = []

    async def _explode(client, pipeline, src, *, limit=200, alert=True, now=None):
        tentadas.append(src.username or "")
        raise RuntimeError("FloodWait")

    monkeypatch.setattr("garimpo.ingest.listener.recover_source", _explode)
    client = _Client([True, False, True])
    asyncio.run(_drive(client, sources, ticks=3, recover=_explode))
    assert tentadas == ["a", "b"], "uma fonte que falha não impede as outras"


def test_probe_failure_is_survivable(monkeypatch, sources) -> None:
    class _Quebrado(_Client):
        def is_connected(self) -> bool:
            self.sondagens += 1
            raise OSError("socket sumiu")

    async def _fake(client, pipeline, src, *, limit=200, alert=True, now=None):
        return 0

    monkeypatch.setattr("garimpo.ingest.listener.recover_source", _fake)
    client = _Quebrado([])
    asyncio.run(_drive(client, sources, ticks=3, recover=_fake))
    assert client.sondagens >= 3

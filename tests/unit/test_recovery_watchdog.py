"""Recuperar a lacuna quando a conexão volta — sem virar polling nem inundar.

run_daemon recuperava lacunas só no boot. O Telethon reconecta sozinho, então
o processo sobrevive a uma queda e retoma os eventos dali em diante: as
mensagens do intervalo nunca eram buscadas, em silêncio.
"""

from __future__ import annotations

import asyncio
from datetime import timedelta

import pytest

from garimpo.ingest.base import SourceRef
from garimpo.ingest.listener import IngestClock, recovery_watchdog


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


async def _drive(client, sources, *, ticks: int, recover=None, **kwargs) -> None:
    """Roda o laço por `ticks` sondagens e para."""
    stop = asyncio.Event()

    async def _parar() -> None:
        while client.sondagens < ticks:
            await asyncio.sleep(0)
        stop.set()

    await asyncio.gather(
        recovery_watchdog(
            client, _Pipeline(), sources, stop, interval_s=0.001, **kwargs
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


# --- Gatilho 2: ingestão parada -------------------------------------------
# O gatilho de socket não basta. Com o macOS dormindo, o processo é suspenso e
# o socket fica ESTABLISHED na tabela do kernel; ao acordar, is_connected()
# segue True. Observado: 54 min sem receber nada, socket vivo, uptime de 2h53.


def test_stalled_ingest_triggers_recovery_even_while_connected(
    monkeypatch, sources
) -> None:
    chamadas: list[str] = []

    async def _fake(client, pipeline, src, *, limit=200, alert=True, now=None):
        chamadas.append(src.username or "")
        return 1

    monkeypatch.setattr("garimpo.ingest.listener.recover_source", _fake)
    clock = IngestClock()
    clock.last -= timedelta(hours=1)  # uma hora sem nada entrar
    client = _Client([True, True])
    asyncio.run(
        _drive(
            client, sources, ticks=2,
            clock=clock, stale_after=timedelta(minutes=30),
        )
    )
    assert chamadas == ["a", "b"], "silêncio longo deve recuperar mesmo conectado"


def test_recent_ingest_does_not_trigger(monkeypatch, sources) -> None:
    chamadas: list[str] = []

    async def _fake(client, pipeline, src, *, limit=200, alert=True, now=None):
        chamadas.append(src.username or "")
        return 0

    monkeypatch.setattr("garimpo.ingest.listener.recover_source", _fake)
    client = _Client([True, True, True])
    asyncio.run(
        _drive(
            client, sources, ticks=3,
            clock=IngestClock(), stale_after=timedelta(minutes=30),
        )
    )
    assert chamadas == [], "canal ativo não deve disparar varredura"


def test_stale_trigger_does_not_fire_every_tick(monkeypatch, sources) -> None:
    """Sem resetar o relógio, um canal quieto viraria 7 chamadas a cada 30s."""
    chamadas: list[str] = []

    async def _fake(client, pipeline, src, *, limit=200, alert=True, now=None):
        chamadas.append(src.username or "")
        return 0

    monkeypatch.setattr("garimpo.ingest.listener.recover_source", _fake)
    clock = IngestClock()
    clock.last -= timedelta(hours=1)
    client = _Client([True, True, True, True])
    asyncio.run(
        _drive(
            client, sources, ticks=4,
            clock=clock, stale_after=timedelta(minutes=30),
        )
    )
    assert len(chamadas) == len(sources), "deve recuperar uma vez, não a cada tick"


def test_without_clock_only_the_socket_trigger_applies(monkeypatch, sources) -> None:
    """Compatibilidade: chamado sem relógio, comporta-se como antes."""
    chamadas: list[str] = []

    async def _fake(client, pipeline, src, *, limit=200, alert=True, now=None):
        chamadas.append(src.username or "")
        return 0

    monkeypatch.setattr("garimpo.ingest.listener.recover_source", _fake)
    client = _Client([True, True, True])
    asyncio.run(_drive(client, sources, ticks=3))
    assert chamadas == []

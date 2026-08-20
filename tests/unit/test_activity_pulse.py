"""Pulso periódico: um daemon saudável não pode parecer morto.

81% do tráfego destes canais é triaged_out — cadeira, filamento, teclado — e o
pipeline manda isso para DEBUG de propósito. Em INFO o log fica parado por
horas, e foi exatamente essa dúvida ("chegou no Telegram e não apareceu no
log") que motivou este pulso.
"""

from __future__ import annotations

import asyncio
from datetime import timedelta

import structlog

from garimpo.ingest.listener import IngestClock, LiveStats, activity_pulse


async def _one_beat(stats: LiveStats, clock: IngestClock) -> None:
    stop = asyncio.Event()

    async def _parar() -> None:
        await asyncio.sleep(0.05)
        stop.set()

    await asyncio.gather(
        activity_pulse(stats, clock, stop, interval_minutes=0.0003),
        _parar(),
    )


def _captura() -> list[dict]:
    saida: list[dict] = []
    structlog.configure(
        processors=[lambda _l, _m, ed: saida.append(ed) or ed],
        logger_factory=structlog.ReturnLoggerFactory(),
        cache_logger_on_first_use=False,
    )
    return saida


def test_pulse_reports_what_was_seen() -> None:
    saida = _captura()
    stats = LiveStats()
    for _ in range(4):
        stats.record("triaged_out")
    stats.record("parsed")
    asyncio.run(_one_beat(stats, IngestClock()))

    pulsos = [e for e in saida if e.get("event") == "pulse"]
    assert pulsos, "o pulso precisa sair"
    assert pulsos[0]["total"] == 5
    assert pulsos[0]["triaged_out"] == 4
    assert pulsos[0]["parsed"] == 1


def test_pulse_fires_even_with_nothing_to_report() -> None:
    """total=0 é o sinal de que algo está errado — calar não ajudaria."""
    saida = _captura()
    asyncio.run(_one_beat(LiveStats(), IngestClock()))
    pulsos = [e for e in saida if e.get("event") == "pulse"]
    assert pulsos and pulsos[0]["total"] == 0


def test_pulse_reports_how_long_ingestion_has_been_silent() -> None:
    saida = _captura()
    clock = IngestClock()
    clock.last -= timedelta(minutes=42)
    asyncio.run(_one_beat(LiveStats(), clock))
    assert [e for e in saida if e.get("event") == "pulse"][0]["silent_min"] >= 42


def test_counters_reset_between_beats() -> None:
    """Sem o reset, o pulso viraria acumulado e não taxa."""
    stats = LiveStats()
    stats.record("parsed")
    primeiro, _ = stats.drain()
    segundo, _ = stats.drain()
    assert primeiro == {"parsed": 1}
    assert segundo == {}

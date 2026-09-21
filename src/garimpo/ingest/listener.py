"""Listener loop: resolve sources, gap recovery, then live events."""

from __future__ import annotations

import asyncio
from collections import Counter
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

import structlog

from garimpo.alert.quiet import in_quiet_hours
from garimpo.ingest.base import MTProtoClient, SourceRef
from garimpo.ingest.recovery import recover_source
from garimpo.models.raw import RawMessage
from garimpo.pipeline import Pipeline

log = structlog.get_logger(__name__)


class NoSourcesResolvedError(RuntimeError):
    """Every configured source failed to resolve."""

    def __init__(self, failures: list[tuple[str, str]]) -> None:
        detail = "\n".join(f"  • {label}: {err}" for label, err in failures)
        super().__init__(
            "Nenhuma source pôde ser resolvida no Telegram:\n"
            f"{detail}\n\n"
            "Verifique em config.yaml, na chave sources:\n"
            "  • o @username está correto (sem o @ também funciona)\n"
            "  • o grupo/canal existe e é público, ou a conta já é membro\n"
            "  • para grupos privados, entre com a conta secundária primeiro"
        )


async def resolve_sources(
    client: MTProtoClient, sources: list[SourceRef]
) -> list[SourceRef]:
    """Resolve sources, skipping the ones Telegram refuses.

    A typo or an unjoined group should cost you that one source, not the whole
    daemon with a raw Telethon traceback.
    """
    resolved: list[SourceRef] = []
    failures: list[tuple[str, str]] = []
    for src in sources:
        label = src.username or str(src.tg_id)
        try:
            resolved.append(await client.resolve_source(src))
        except Exception as exc:  # noqa: BLE001 - backend-specific error zoo
            failures.append((label, str(exc)))
            log.warning("source_unresolved", source=label, error=str(exc))

    if failures and not resolved:
        raise NoSourcesResolvedError(failures)
    if failures:
        log.warning(
            "sources_partially_resolved",
            ok=len(resolved),
            failed=len(failures),
        )
    log.info(
        "sources_ready",
        sources=[s.username or str(s.tg_id) for s in resolved],
    )
    return resolved


async def run_once(
    client: MTProtoClient,
    pipeline: Pipeline,
    sources: list[SourceRef],
) -> int:
    """Single pass gap recovery across all sources, then stop."""
    await client.start()
    total = 0
    try:
        resolved = await resolve_sources(client, sources)
        for src in resolved:
            total += await recover_source(client, pipeline, src, alert=True)
        pipeline.purge_expired()
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
    resolved = await resolve_sources(client, sources)

    for src in resolved:
        await recover_source(client, pipeline, src, alert=True)

    clock = IngestClock()
    stats = LiveStats()

    async def _handle(msg: RawMessage) -> None:
        clock.touch()
        resultado = pipeline.process(msg)
        lag_s = (msg.received_at - msg.posted_at).total_seconds() if msg.posted_at else None
        stats.record(resultado.status, lag_s=lag_s)
        from garimpo.ingest.recovery import set_last_msg_id

        set_last_msg_id(pipeline.conn, msg.source_id, msg.tg_msg_id)

    client.on_new_message(resolved, _handle)

    stop = stop_event or asyncio.Event()
    tasks: list[asyncio.Task[None]] = [
        asyncio.create_task(_quiet_flush_loop(pipeline, stop)),
        asyncio.create_task(
            activity_pulse(
                stats,
                clock,
                stop,
                interval_minutes=pipeline.settings.health.pulse_minutes,
            )
        ),
        asyncio.create_task(_retention_loop(pipeline, stop)),
        asyncio.create_task(
            recovery_watchdog(
                client,
                pipeline,
                resolved,
                stop,
                clock=clock,
                stale_after=timedelta(
                    minutes=pipeline.settings.health.stale_ingest_minutes
                ),
            )
        ),
    ]

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


class IngestClock:
    """Quando a última mensagem entrou de fato.

    Compartilhado entre o handler ao vivo e o watchdog. Ler isto é comparação
    de timestamp em memória — nunca uma chamada ao Telegram.
    """

    __slots__ = ("last",)

    def __init__(self) -> None:
        self.last = datetime.now(UTC)

    def touch(self) -> None:
        self.last = datetime.now(UTC)

    def silent_for(self, now: datetime | None = None) -> timedelta:
        return (now or datetime.now(UTC)) - self.last


async def recovery_watchdog(
    client: MTProtoClient,
    pipeline: Pipeline,
    sources: list[SourceRef],
    stop: asyncio.Event,
    *,
    interval_s: float = 30.0,
    clock: IngestClock | None = None,
    stale_after: timedelta | None = None,
) -> None:
    """Refaz o gap recovery quando o daemon volta a si. Dois gatilhos.

    `run_daemon` recupera lacunas uma vez, no boot, e depois só escuta eventos
    ao vivo. Processo suspenso e retomado não é processo reiniciado, e a
    diferença é invisível: nada no log diz que houve buraco.

    **Reconexão** — o Telethon reconecta sozinho depois de uma queda de rede,
    e retoma os eventos a partir dali. `is_connected()` lê estado em memória e
    nunca fala com o Telegram, então isto é detecção de transição, não polling.

    **Ingestão parada** — o gatilho acima não basta. Quando o macOS dorme, o
    processo é suspenso e o socket fica na tabela do kernel parecendo
    ESTABLISHED; ao acordar, `is_connected()` continua `True` e nada indica que
    houve buraco. Observado na prática: 54 minutos sem receber nada, com o
    socket vivo e o processo com quase três horas de uptime. Por isso o segundo
    gatilho olha para o *dado*: silêncio em TODAS as fontes por mais de
    `stale_after` é tratado como conexão morta.

    Também custa zero com tudo saudável — é comparação de timestamp em memória.
    Quando dispara sem necessidade, porque os canais estavam genuinamente
    quietos, o custo é um fetch por fonte devolvendo zero.

    `alert=True` de propósito: uma queda de dois minutos deve alertar
    normalmente. Quem impede a enxurrada depois de uma noite offline é o
    ALERT_MAX_AGE dentro de `recover_source`, que cala tudo com mais de 15
    minutos. Trocar por `alert=False` perderia oferta legítima de reconexão
    rápida.
    """
    estava_conectado = True
    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval_s)
            return
        except TimeoutError:
            pass

        try:
            conectado = client.is_connected()
        except Exception as exc:  # noqa: BLE001 - nunca derrubar o daemon
            log.debug("watchdog_probe_failed", error=str(exc))
            continue

        motivo: str | None = None
        if conectado and not estava_conectado:
            motivo = "reconnected"
        elif conectado and clock is not None and stale_after is not None:
            calado = clock.silent_for()
            if calado > stale_after:
                motivo = "stale_ingest"
                log.warning(
                    "ingest_stale", silent_minutes=round(calado.total_seconds() / 60)
                )
        elif estava_conectado and not conectado:
            log.warning("disconnected_waiting_reconnect")

        if motivo is not None:
            log.info("watchdog_recovering", reason=motivo, sources=len(sources))
            recuperadas = 0
            for src in sources:
                try:
                    recuperadas += await recover_source(
                        client, pipeline, src, alert=True
                    )
                except Exception as exc:  # noqa: BLE001
                    label = src.username or str(src.tg_id)
                    log.warning("watchdog_recovery_failed", source=label, error=str(exc))
            log.info("watchdog_recovered", reason=motivo, messages=recuperadas)
            # Sem isto, o gatilho de silêncio dispara a cada tick enquanto o
            # canal estiver genuinamente quieto — sete chamadas a cada 30s.
            if clock is not None:
                clock.touch()

        estava_conectado = conectado


class LiveStats:
    """Contagem por status desde o último pulso.

    Em memória de propósito: o pulso é para dizer que o daemon está vivo, e
    consultar o banco a cada 15 minutos para descobrir isso seria trocar um
    problema barato por um caro.
    """

    __slots__ = ("_atrasos", "_contagem", "desde")

    def __init__(self) -> None:
        self._contagem: Counter[str] = Counter()
        self._atrasos: list[float] = []
        self.desde = datetime.now(UTC)

    def record(self, status: str, *, lag_s: float | None = None) -> None:
        self._contagem[status] += 1
        if lag_s is not None:
            self._atrasos.append(lag_s)

    def drain_lag(self) -> dict[str, float]:
        """Mediana e máximo de (recebida - postada) na janela, em segundos.

        Só mensagens que chegaram pelo evento ao vivo; as do gap recovery são
        atrasadas por definição e não dizem nada sobre a entrega do Telegram.
        """
        atrasos = sorted(self._atrasos)
        self._atrasos.clear()
        if not atrasos:
            return {}
        return {
            "lag_p50_s": round(atrasos[len(atrasos) // 2], 1),
            "lag_max_s": round(atrasos[-1], 1),
        }

    def drain(self) -> tuple[dict[str, int], timedelta]:
        contagem = dict(self._contagem)
        janela = datetime.now(UTC) - self.desde
        self._contagem.clear()
        self.desde = datetime.now(UTC)
        return contagem, janela


async def activity_pulse(
    stats: LiveStats,
    clock: IngestClock,
    stop: asyncio.Event,
    *,
    interval_minutes: float = 15.0,
) -> None:
    """Uma linha periódica dizendo que o daemon está vivo e o que viu.

    81% do tráfego destes canais é `triaged_out` — cadeira de escritório,
    filamento de impressora, teclado — e o pipeline manda isso para DEBUG de
    propósito, senão as decisões que importam ficariam enterradas. O efeito
    colateral é que, em INFO, o log fica parado por horas e um daemon saudável
    é indistinguível de um morto. Foi exatamente essa dúvida que motivou isto.

    Loga sempre, inclusive quando não houve nada: um pulso com `total=0` é o
    sinal de que algo está errado, e é justamente o caso em que ficar calado
    não ajudaria ninguém.

    Não fala com o Telegram nem com o banco — só lê contadores em memória.
    """
    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval_minutes * 60)
            return
        except TimeoutError:
            pass

        atraso = stats.drain_lag()
        contagem, janela = stats.drain()
        calado = clock.silent_for()
        log.info(
            "pulse",
            window_min=round(janela.total_seconds() / 60, 1),
            total=sum(contagem.values()),
            silent_min=round(calado.total_seconds() / 60, 1),
            **atraso,
            **contagem,
        )


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


async def _retention_loop(
    pipeline: Pipeline,
    stop: asyncio.Event,
    *,
    interval_hours: float = 6.0,
) -> None:
    """Keep raw_messages bounded — a 24/7 daemon otherwise grows forever."""
    while not stop.is_set():
        pipeline.purge_expired()
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval_hours * 3600)
        except TimeoutError:
            continue


def sync_run(coro_factory: Callable[[], Awaitable[object]]) -> object:
    return asyncio.run(coro_factory())

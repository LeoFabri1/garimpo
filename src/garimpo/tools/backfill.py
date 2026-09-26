"""CSV backfill into price_history.

CSV columns: model_key,price,store,observed_at[,condition]
"""

from __future__ import annotations

import csv
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from garimpo.settings import Settings
from garimpo.store.db import connect
from garimpo.store.repo import history as history_repo


def backfill_csv(
    db_path: str | Path,
    csv_path: Path,
    *,
    origin: str = "backfill",
) -> int:
    conn = connect(db_path)
    inserted = 0
    try:
        with csv_path.open(encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            required = {"model_key", "price", "observed_at"}
            if reader.fieldnames is None or not required.issubset(set(reader.fieldnames)):
                raise ValueError(
                    "CSV precisa das colunas: model_key,price,observed_at[,store,condition]"
                )
            for row in reader:
                observed = _parse_dt(row["observed_at"])
                store = row.get("store") or None
                condition = row.get("condition") or "new"
                rid = history_repo.insert_history(
                    conn,
                    model_key=row["model_key"].strip(),
                    price=float(row["price"]),
                    observed_at=observed,
                    origin=origin,
                    condition=condition.strip(),
                    store=store.strip() if store else None,
                )
                if rid is not None:
                    inserted += 1
    finally:
        conn.close()
    return inserted


def _parse_dt(value: str) -> datetime:
    value = value.strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return datetime.fromisoformat(value)


async def backfill_telegram(
    settings: Settings,
    *,
    days: int = 90,
    batch: int = 1000,
    max_batches: int = 60,
    progress: Callable[[str], None] = print,
) -> dict[str, int]:
    """Puxa o histórico recente de cada fonte configurada.

    Existe porque `run --once` faz *gap recovery*, não backfill: com
    `last_msg_id = 0` ele parte da primeira mensagem do canal, e num grupo
    ativo desde 2020 isso são as 200 mensagens mais antigas — preço de cinco
    anos atrás, silenciosamente. Semear o ponteiro à mão era o primeiro de
    quatro scripts avulsos que um usuário novo precisava escrever.

    Nunca alerta: um backfill de 90 dias disparando notificação seria
    milhares de mensagens de uma vez.
    """
    from garimpo.alert.channels.console import ConsoleChannel
    from garimpo.ingest.factory import build_client
    from garimpo.ingest.recovery import get_last_msg_id, recover_source, set_last_msg_id
    from garimpo.ingest.sources import sources_from_settings
    from garimpo.pipeline import Pipeline
    from garimpo.store.repo import messages as messages_repo

    client = build_client(settings)
    # Canal console explícito, NÃO dry_run: o backfill precisa gravar no banco
    # real, e dry_run agora usa banco em memória. O console evita exigir um
    # cliente Telegram conectado quando alerts.channel = saved_messages.
    pipe = Pipeline(settings, channel=ConsoleChannel())
    total: dict[str, int] = {}
    await client.start()
    try:
        for src in sources_from_settings(settings):
            label = src.username or str(src.tg_id)
            try:
                resolved = await client.resolve_source(src)
            except Exception as exc:  # noqa: BLE001 - zoo de erros por backend
                progress(f"  ✗ {label}: não resolveu — {exc}")
                total[label] = -1
                continue
            if resolved.tg_id is None:
                progress(f"  ✗ {label}: sem tg_id após resolver")
                total[label] = -1
                continue

            messages_repo.ensure_source(
                pipe.conn,
                tg_id=resolved.tg_id,
                username=resolved.username,
                parser=resolved.parser,
            )

            # O ponteiro precisa RECUAR para `days` atrás, mesmo numa fonte já
            # ingerida. Antes isto só valia para last_msg_id == 0, e como
            # `fetch_since` pede o que é mais NOVO que o ponteiro, um backfill
            # sobre fonte ativa não lia nada e imprimia "✓ 0 mensagens" — que
            # se lê como "o canal não tinha nada". Foi assim que um apagão de
            # 16 dias em 7 das 8 fontes ficou aparentemente irrecuperável.
            atual = get_last_msg_id(pipe.conn, resolved.tg_id)
            try:
                inicio = await client.msg_id_at(resolved, days)
            except NotImplementedError:
                inicio = 0
                if atual == 0:
                    progress(f"  ⚠ {label}: backend sem msg_id_at — começando do início do canal")
            # Só recua. Avançar pularia calado as mensagens entre os dois
            # pontos, e reprocessar o que já existe é barato: a inserção de
            # raw_message devolve a linha existente no conflito.
            if inicio and (atual == 0 or inicio < atual):
                set_last_msg_id(pipe.conn, resolved.tg_id, inicio)
                progress(f"  {label}: voltando para msg_id={inicio} (~{days}d atrás)")

            n = 0
            for _ in range(max_batches):
                got = await recover_source(
                    client, pipe, resolved, limit=batch, alert=False
                )
                n += got
                if got == 0:
                    break
            total[label] = n
            progress(f"  ✓ {label}: {n} mensagens")
    finally:
        await client.stop()
        pipe.close()
    return total

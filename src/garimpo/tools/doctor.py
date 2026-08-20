"""garimpo doctor — local configuration diagnostics, no network."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from garimpo.catalog import ModelIndex, load_gpu_catalog
from garimpo.settings import Settings, find_config_path, load_settings
from garimpo.store.db import connect, user_version


@dataclass
class CheckResult:
    ok: bool
    label: str
    detail: str | None = None
    warn: bool = False


def run_doctor(*, config: Path | None = None, quick: bool = False) -> list[CheckResult]:
    from garimpo.auth.login import load_dotenv_if_present

    load_dotenv_if_present()
    results: list[CheckResult] = []

    config_path = find_config_path(config)
    if not config_path.is_file():
        results.append(
            CheckResult(
                False,
                "config.yaml",
                f"não encontrado em {config_path}. "
                "Copie config/quickstart.yaml → config/config.yaml",
            )
        )
        return results

    try:
        settings = load_settings(config_path)
        results.append(CheckResult(True, "config.yaml válido", str(config_path)))
    except Exception as exc:  # noqa: BLE001 — doctor must surface any validation error
        results.append(CheckResult(False, "config.yaml válido", str(exc)))
        return results

    # Env vars referenced by telegram
    for env_name, label in [
        (settings.telegram.api_id_env, "TG_API_ID"),
        (settings.telegram.api_hash_env, "TG_API_HASH"),
    ]:
        if os.environ.get(env_name):
            results.append(CheckResult(True, f"{label} presente", env_name))
        else:
            results.append(
                CheckResult(
                    True,
                    f"{label} ausente",
                    f"defina {env_name} no .env — necessário para `garimpo login`",
                    warn=True,
                )
            )

    # Catalog + watch models
    try:
        catalog = load_gpu_catalog()
        index = ModelIndex(catalog)
        results.append(
            CheckResult(True, "catálogo GPU", f"{len(catalog.products)} modelos")
        )
    except Exception as exc:  # noqa: BLE001
        results.append(CheckResult(False, "catálogo GPU", str(exc)))
        return results

    missing: list[str] = []
    for rule in settings.watch:
        if not rule.models:
            continue
        for name in rule.models:
            hit = index.resolve(name)
            if hit is None and name not in catalog.products:
                missing.append(name)
    if missing:
        results.append(
            CheckResult(
                False,
                "modelos do watch no catálogo",
                "não encontrados: " + ", ".join(missing),
            )
        )
    else:
        n = sum(len(r.models or []) for r in settings.watch)
        results.append(CheckResult(True, "modelos do watch no catálogo", f"{n} ok"))

    # Storage path / migrate
    try:
        db_path = Path(settings.storage.path)
        conn = connect(db_path)
        ver = user_version(conn)
        conn.close()
        results.append(
            CheckResult(True, "SQLite + migrations", f"{db_path} (user_version={ver})")
        )
    except Exception as exc:  # noqa: BLE001
        results.append(CheckResult(False, "SQLite + migrations", str(exc)))

    if not settings.watch:
        results.append(
            CheckResult(False, "watch rules", "nenhuma regra em watch — nada será alertado")
        )
    else:
        results.append(CheckResult(True, "watch rules", f"{len(settings.watch)} regra(s)"))

    results.append(_check_alert_channel(settings))

    # Warn, not fail: --dry-run and -m are legitimate without any source.
    enabled_sources = [s for s in settings.sources if s.enabled]
    if not enabled_sources:
        results.append(
            CheckResult(
                True,
                "sources",
                "nenhuma configurada — `run --dry-run` funciona, mas o run "
                "ao vivo vai parar. Adicione seus canais em sources:",
                warn=True,
            )
        )
    else:
        labels = ", ".join(
            f"@{s.username}" if s.username else str(s.id) for s in enabled_sources
        )
        results.append(
            CheckResult(True, "sources", f"{len(enabled_sources)}: {labels}")
        )

    # Session file (informational until `garimpo login` runs)
    session = Path(settings.telegram.session)
    if session.is_file():
        results.append(CheckResult(True, "arquivo de sessão", str(session)))
        if not quick:
            results.extend(_check_session_auth(settings))
    else:
        results.append(
            CheckResult(
                True,
                "arquivo de sessão",
                f"ainda não existe ({session}) — esperado até `garimpo login`",
                warn=True,
            )
        )

    return results


def _check_alert_channel(settings: Settings) -> CheckResult:
    """A channel that cannot deliver is worse than no alerts: it fails at the
    moment a deal fires, which is exactly when nobody is watching the logs."""
    from garimpo.settings import BotSettings, WebhookSettings

    channel = settings.alerts.channel
    if channel == "console":
        return CheckResult(True, "canal de alerta", "console (terminal)")

    if channel == "saved_messages":
        return CheckResult(
            True, "canal de alerta", "saved_messages — usa a sessão do Telegram"
        )

    if channel == "bot":
        bot = settings.alerts.bot or BotSettings()
        missing = [
            name
            for name in (bot.token_env, bot.chat_id_env)
            if not os.environ.get(name)
        ]
        if missing:
            return CheckResult(
                False,
                "canal de alerta",
                f"bot, mas falta no .env: {', '.join(missing)}",
            )
        return CheckResult(True, "canal de alerta", "bot (Bot API)")

    wh = settings.alerts.webhook or WebhookSettings()
    if not os.environ.get(wh.url_env):
        return CheckResult(
            False, "canal de alerta", f"webhook, mas falta no .env: {wh.url_env}"
        )
    return CheckResult(True, "canal de alerta", "webhook")


_RESOLVE_TIMEOUT_S = 15.0


async def _resolve_sources(client: object, settings: object) -> list[CheckResult]:
    """Resolve cada source contra o Telegram, uma linha por fonte.

    Sem isto o check de sources só conta linhas do YAML: username errado passa
    no doctor, vira um warning no meio do `run`, e o daemon segue com menos
    fontes do que você pediu sem que ninguém perceba.

    Nunca derruba o comando. Diagnóstico que quebra por causa de rede é pior
    que diagnóstico incompleto — por isso timeout por fonte e captura ampla.
    """
    import asyncio

    from garimpo.ingest.sources import sources_from_settings

    fontes = sources_from_settings(settings)  # type: ignore[arg-type]
    if not fontes:
        return []

    out: list[CheckResult] = []
    for src in fontes:
        label = f"@{src.username}" if src.username else str(src.tg_id)
        try:
            resolvida = await asyncio.wait_for(
                client.resolve_source(src),  # type: ignore[attr-defined]
                timeout=_RESOLVE_TIMEOUT_S,
            )
        except TimeoutError:
            out.append(
                CheckResult(True, f"source {label}", "timeout ao resolver", warn=True)
            )
        except Exception as exc:  # noqa: BLE001 - zoo de erros por backend
            out.append(CheckResult(False, f"source {label}", f"não resolve — {exc}"))
        else:
            out.append(
                CheckResult(True, f"source {label}", f"ok (tg_id={resolvida.tg_id})")
            )
    return out


def _check_session_auth(settings: object) -> list[CheckResult]:
    import asyncio

    try:
        from garimpo.ingest.factory import build_client

        client = build_client(settings)  # type: ignore[arg-type]

        async def _probe() -> tuple[bool, list[CheckResult]]:
            try:
                ok = await client.is_authorized()
                # Mesma conexão: abrir um segundo cliente só para resolver
                # sources custaria outro handshake por diagnóstico.
                extras = await _resolve_sources(client, settings) if ok else []
                await client.stop()
                return bool(ok), extras
            except Exception:
                try:
                    await client.stop()
                except Exception:  # noqa: BLE001
                    pass
                raise

        authorized, source_checks = asyncio.run(_probe())
        if authorized:
            return [CheckResult(True, "sessão autenticada", "ok"), *source_checks]
        return [
            CheckResult(
                False,
                "sessão autenticada",
                "arquivo existe mas não autoriza — rode: garimpo login --qr",
            )
        ]
    except Exception as exc:  # noqa: BLE001
        # O arquivo .session é um SQLite e não aceita dois donos. Com o daemon
        # de pé, `doctor` sempre bate nisso — e "database is locked" não diz
        # nada a quem só quer saber se está tudo certo.
        if "database is locked" in str(exc).lower():
            detalhe = (
                "o daemon está usando a sessão — pare-o para verificar, "
                "ou rode `garimpo doctor --quick`"
            )
        else:
            detalhe = f"não verificado ({exc})"
        return [CheckResult(True, "sessão autenticada", detalhe, warn=True)]


def format_results(results: list[CheckResult]) -> str:
    lines: list[str] = []
    for r in results:
        if r.ok and r.warn:
            mark = "⚠"
        elif r.ok:
            mark = "✓"
        else:
            mark = "✗"
        detail = f" — {r.detail}" if r.detail else ""
        lines.append(f"{mark} {r.label}{detail}")
    return "\n".join(lines)


def exit_code(results: list[CheckResult]) -> int:
    # warnings (ok=True, warn=True) don't fail; hard failures do
    return 1 if any(not r.ok for r in results) else 0

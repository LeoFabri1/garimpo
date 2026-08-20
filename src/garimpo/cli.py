"""CLI entrypoint (Typer)."""

from __future__ import annotations

from pathlib import Path

import typer

from garimpo import __version__

app = typer.Typer(
    name="garimpo",
    help="Deal prospecting engine for Telegram — alerts only on statistically exceptional prices.",
    no_args_is_help=True,
)

catalog_app = typer.Typer(help="Catalog tools")
app.add_typer(catalog_app, name="catalog")


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        help="Show version and exit.",
    ),
) -> None:
    if version:
        typer.echo(f"garimpo {__version__}")
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


@app.command("doctor")
def doctor_cmd(
    quick: bool = typer.Option(False, "--quick", help="Skip slow connectivity checks."),
    config: Path | None = typer.Option(
        None, "--config", "-c", help="Path to config YAML."
    ),
) -> None:
    """Diagnose configuration and (optionally) Telegram session."""
    from garimpo.tools.doctor import exit_code, format_results, run_doctor

    results = run_doctor(config=config, quick=quick)
    typer.echo(format_results(results))
    raise typer.Exit(code=exit_code(results))


@app.command("login")
def login_cmd(
    qr: bool = typer.Option(True, "--qr/--code", help="QR login (default) or phone code."),
    export_string: bool = typer.Option(
        False, "--export-string", help="Print StringSession once (for ephemeral hosts)."
    ),
    password: str | None = typer.Option(
        None, "--password", help="2FA password if required."
    ),
    phone: str | None = typer.Option(None, "--phone", help="Phone for --code login."),
    i_understand: bool = typer.Option(
        False,
        "--i-understand",
        help="Skip risk confirmation (CI). Still use a secondary number.",
    ),
    config: Path | None = typer.Option(
        None, "--config", "-c", help="Path to config YAML."
    ),
) -> None:
    """Authenticate Telegram session. Requires secondary number acknowledgement."""
    import asyncio

    from garimpo.auth.errors import LoginAborted, LoginConfigError
    from garimpo.auth.login import load_dotenv_if_present, run_login
    from garimpo.settings import load_settings

    load_dotenv_if_present()
    settings = load_settings(config)
    try:
        asyncio.run(
            run_login(
                settings,
                use_qr=qr,
                export_string=export_string,
                phone=phone,
                password=password,
                skip_risk_confirm=i_understand,
            )
        )
    except (LoginConfigError, LoginAborted) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc


@app.command("logout")
def logout_cmd(
    local_only: bool = typer.Option(
        False,
        "--local-only",
        help="Só apaga o arquivo local; a sessão SEGUE ativa no Telegram.",
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Não pedir confirmação."),
    config: Path | None = typer.Option(
        None, "--config", "-c", help="Path to config YAML."
    ),
) -> None:
    """Revoke the Telegram session server-side and remove the local file."""
    import asyncio

    from garimpo.auth.login import load_dotenv_if_present
    from garimpo.auth.logout import run_logout
    from garimpo.settings import load_settings

    load_dotenv_if_present()
    settings = load_settings(config)

    if not yes:
        target = "arquivo local (sessão segue ativa)" if local_only else "sessão"
        typer.echo(f"Isto vai remover a {target}. Você precisará de novo login.")
        if not typer.confirm("Continuar?"):
            typer.echo("cancelado")
            raise typer.Exit(code=1)

    result = asyncio.run(run_logout(settings, local_only=local_only))
    mark = "✓" if (result.revoked or result.file_removed) else "•"
    typer.echo(f"{mark} {result.detail}")


@app.command("run")
def run_cmd(
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Process fixture/demo without Telegram."
    ),
    once: bool = typer.Option(
        False, "--once", help="Single gap-recovery pass then exit."
    ),
    config: Path | None = typer.Option(
        None, "--config", "-c", help="Path to config YAML."
    ),
    message: list[str] | None = typer.Option(
        None,
        "--message",
        "-m",
        help="Message text to process (repeatable). Offline pipeline.",
    ),
) -> None:
    """Run daemon, --once pass, or offline --dry-run / -m pipeline."""
    from garimpo.auth.login import load_dotenv_if_present
    from garimpo.logging import configure_logging
    from garimpo.settings import load_settings

    load_dotenv_if_present()
    settings = load_settings(config)
    configure_logging(level=settings.logging.level, fmt=settings.logging.format)

    if dry_run or message:
        from garimpo.pipeline import process_texts

        texts = list(message or [])
        if not texts:
            texts = ["🚨 RTX 5070 Ti ASUS Dual — R$ 5.799 no PIX na Kabum"]
            typer.echo("(sem -m: usando mensagem demo)\n")
        results = process_texts(settings, texts, dry_run=True)
        for r in results:
            level = r.scored.level.value if r.scored else "-"
            typer.echo(
                f"→ status={r.status} raw_id={r.raw_id} offer_id={r.offer_id} level={level}"
            )
        return

    # Live Telegram
    import asyncio

    from garimpo.ingest.factory import build_client
    from garimpo.ingest.listener import NoSourcesResolvedError, run_daemon, run_once
    from garimpo.ingest.sources import sources_from_settings
    from garimpo.pipeline import Pipeline

    sources = sources_from_settings(settings)
    if not sources:
        typer.echo("Nenhuma source em config. Adicione sources: no YAML.", err=True)
        raise typer.Exit(code=1)

    client = build_client(settings)
    pipeline = Pipeline(settings, dry_run=False, client=client)
    try:
        if once:
            n = asyncio.run(run_once(client, pipeline, sources))
            typer.echo(f"processed {n} message(s) (--once)")
        else:
            typer.echo("garimpo run: listening (Ctrl+C to stop)…")
            try:
                asyncio.run(run_daemon(client, pipeline, sources))
            except KeyboardInterrupt:
                typer.echo("\nstopped")
    except NoSourcesResolvedError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    finally:
        pipeline.close()


@app.command("stats")
def stats_cmd(
    config: Path | None = typer.Option(
        None, "--config", "-c", help="Path to config YAML."
    ),
) -> None:
    """Show local DB counters."""
    import json

    from garimpo.pipeline import stats_snapshot
    from garimpo.settings import load_settings

    settings = load_settings(config)
    typer.echo(json.dumps(stats_snapshot(settings), indent=2, ensure_ascii=False))


@app.command("backfill")
def backfill_cmd(
    csv_file: Path | None = typer.Argument(None, exists=True, dir_okay=False),
    telegram: bool = typer.Option(
        False, "--telegram", help="Puxa o histórico recente das sources do config."
    ),
    days: int = typer.Option(90, "--days", help="Janela do backfill --telegram."),
    origin: str = typer.Option("backfill", "--origin"),
    config: Path | None = typer.Option(
        None, "--config", "-c", help="Path to config YAML."
    ),
) -> None:
    """Popula o histórico de preço: de um CSV, ou do Telegram com --telegram.

    `run --once` faz gap recovery e parte da mensagem mais antiga do canal.
    Para começar, use `backfill --telegram --days 90`.
    """
    import asyncio

    from garimpo.settings import load_settings
    from garimpo.tools.backfill import backfill_csv, backfill_telegram

    settings = load_settings(config)

    if telegram:
        if csv_file is not None:
            raise typer.BadParameter("--telegram não aceita arquivo CSV junto.")
        typer.echo(f"backfill do Telegram, últimos {days} dias:")
        total = asyncio.run(backfill_telegram(settings, days=days, progress=typer.echo))
        ok = sum(v for v in total.values() if v > 0)
        falhas = [k for k, v in total.items() if v < 0]
        typer.echo(f"\n{ok} mensagem(ns) de {len(total) - len(falhas)} fonte(s)")
        if falhas:
            typer.echo(f"não resolveram: {', '.join(falhas)}")
        return

    if csv_file is None:
        raise typer.BadParameter("informe um CSV ou use --telegram.")
    n = backfill_csv(settings.storage.path, csv_file, origin=origin)
    typer.echo(f"inserted {n} row(s) into price_history (origin={origin})")


@app.command("simulate")
def simulate_cmd(
    days: int = typer.Option(90, "--days"),
    config: Path | None = typer.Option(
        None, "--config", "-c", help="Path to config YAML."
    ),
) -> None:
    """Replay stored offers against current watch rules (calibration)."""
    from garimpo.settings import load_settings
    from garimpo.tools.simulate import simulate

    settings = load_settings(config)
    report = simulate(settings, days=days)
    typer.echo(
        f"simulate last {report.days}d — {report.offers} offers → {report.by_level}"
    )


@app.command("reparse")
def reparse_cmd(
    status: str = typer.Option("parse_failed", "--status"),
    since: int = typer.Option(30, "--since", help="Days lookback"),
    config: Path | None = typer.Option(
        None, "--config", "-c", help="Path to config YAML."
    ),
) -> None:
    """Re-run parsers on stored raw messages."""
    from garimpo.settings import load_settings
    from garimpo.tools.reparse import reparse

    settings = load_settings(config)
    n = reparse(settings, status=status, since_days=since, dry_run=True)
    typer.echo(f"reparse: {n} message(s) newly parsed")


@app.command("export")
def export_cmd(
    out: Path = typer.Option(Path("precos.csv"), "--out", "-o"),
    config: Path | None = typer.Option(
        None, "--config", "-c", help="Path to config YAML."
    ),
) -> None:
    """Export price_history to CSV."""
    from garimpo.mcp.queries import export_price_history_csv
    from garimpo.settings import load_settings

    settings = load_settings(config)
    n = export_price_history_csv(settings.storage.path, out)
    typer.echo(f"exported {n} row(s) → {out}")


@app.command("mcp")
def mcp_cmd() -> None:
    """Start read-only MCP server (separate process). Requires --extra mcp."""
    from garimpo.mcp.server import main

    main()


@app.command("panel")
def panel_cmd(
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8765, "--port"),
    config: Path | None = typer.Option(
        None, "--config", "-c", help="Path to config YAML."
    ),
) -> None:
    """Local read-only price panel (binds localhost by default)."""
    from garimpo.settings import load_settings
    from garimpo.web.panel import serve

    settings = load_settings(config)
    typer.echo(f"garimpo panel → http://{host}:{port}/  (Ctrl+C to stop)")
    serve(settings.storage.path, host=host, port=port)


@catalog_app.command("check")
def catalog_check_cmd() -> None:
    """Validate catalog JSON (aliases, collisions, required fields)."""
    from garimpo.tools.catalog_check import check_catalogs

    errors = check_catalogs()
    if errors:
        for err in errors:
            typer.echo(f"✗ {err}", err=True)
        raise typer.Exit(code=1)
    typer.echo("✓ catalogs ok")


@app.command("fixtures-check")
def fixtures_check_cmd() -> None:
    """Reject affiliate links / PII patterns in parser fixtures."""
    from garimpo.tools.fixture_check import check_fixtures

    errors = check_fixtures()
    if errors:
        for err in errors:
            typer.echo(f"✗ {err}", err=True)
        raise typer.Exit(code=1)
    typer.echo("✓ fixtures ok")

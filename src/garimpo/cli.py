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
    """Diagnose configuration (local checks; network in Sprint 3)."""
    from garimpo.tools.doctor import exit_code, format_results, run_doctor

    results = run_doctor(config=config, quick=quick)
    typer.echo(format_results(results))
    raise typer.Exit(code=exit_code(results))


@app.command("run")
def run_cmd(
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Process fixture/demo without Telegram."
    ),
    once: bool = typer.Option(False, "--once", help="Single pass then exit (Sprint 3)."),
    config: Path | None = typer.Option(
        None, "--config", "-c", help="Path to config YAML."
    ),
    message: list[str] | None = typer.Option(
        None,
        "--message",
        "-m",
        help="Message text to process (repeatable). Implies offline pipeline.",
    ),
) -> None:
    """Run the listener daemon, or offline pipeline with --dry-run / --message."""
    from garimpo.logging import configure_logging
    from garimpo.pipeline import process_texts
    from garimpo.settings import load_settings

    if not dry_run and not message:
        typer.echo(
            "garimpo run (daemon): Telegram listener arrives in Sprint 3.\n"
            "Use: garimpo run --dry-run -m 'RTX 5070 Ti R$ 5.799 no PIX Kabum'"
        )
        raise typer.Exit(code=1)

    settings = load_settings(config)
    configure_logging(level=settings.logging.level, fmt=settings.logging.format)

    texts = list(message or [])
    if not texts:
        texts = [
            "🚨 RTX 5070 Ti ASUS Dual — R$ 5.799 no PIX na Kabum",
        ]
        typer.echo("(sem -m: usando mensagem demo)\n")

    results = process_texts(settings, texts, dry_run=True)
    for r in results:
        level = r.scored.level.value if r.scored else "-"
        typer.echo(
            f"→ status={r.status} raw_id={r.raw_id} offer_id={r.offer_id} level={level}"
        )
    _ = once


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
    csv_file: Path = typer.Argument(..., exists=True, dir_okay=False),
    origin: str = typer.Option("backfill", "--origin"),
    config: Path | None = typer.Option(
        None, "--config", "-c", help="Path to config YAML."
    ),
) -> None:
    """Import price history from CSV (model_key,price,store,observed_at)."""
    from garimpo.settings import load_settings
    from garimpo.tools.backfill import backfill_csv

    settings = load_settings(config)
    n = backfill_csv(settings.storage.path, csv_file, origin=origin)
    typer.echo(f"inserted {n} row(s) into price_history (origin={origin})")

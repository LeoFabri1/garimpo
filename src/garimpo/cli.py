"""CLI entrypoint (Typer). Commands grow across sprints; Sprint 0 is scaffold only."""

from __future__ import annotations

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
def doctor(
    quick: bool = typer.Option(False, "--quick", help="Skip slow connectivity checks."),
) -> None:
    """Diagnose configuration and connectivity (stub until Sprint 2)."""
    _ = quick
    typer.echo("garimpo doctor: not implemented yet (Sprint 2).")
    raise typer.Exit(code=1)


@app.command("run")
def run(
    dry_run: bool = typer.Option(False, "--dry-run", help="Process without sending alerts."),
    once: bool = typer.Option(False, "--once", help="Single pass then exit (gap recovery)."),
) -> None:
    """Run the listener daemon (stub until Sprint 3–4)."""
    _ = (dry_run, once)
    typer.echo("garimpo run: not implemented yet (Sprints 3–4).")
    raise typer.Exit(code=1)

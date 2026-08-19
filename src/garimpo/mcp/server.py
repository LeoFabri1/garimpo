"""MCP server process (read-only). Requires optional extra: uv sync --extra mcp."""

from __future__ import annotations

import os


def main() -> None:
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise SystemExit(
            "Pacote MCP não instalado. Rode: uv sync --extra mcp\n"
            "Depois: uv run garimpo mcp"
        ) from exc

    from garimpo.mcp import queries

    db = os.environ.get("GARIMPO_DB", "data/garimpo.db")
    mcp = FastMCP("garimpo")

    @mcp.tool()
    def query_price_history(model: str, days: int = 90, condition: str = "new") -> str:
        """Price series + median/min/max for a model_key."""
        return queries.dumps(
            queries.query_price_history(db, model, days=days, condition=condition)
        )

    @mcp.tool()
    def list_offers(days: int = 30, model: str | None = None) -> str:
        """List recent offers from the local database."""
        return queries.dumps(queries.list_offers(db, days=days, model=model))

    @mcp.tool()
    def list_alerts(days: int = 30, level: str | None = None) -> str:
        """List alerts (sent/deferred/suppressed)."""
        return queries.dumps(queries.list_alerts(db, days=days, level=level))

    @mcp.tool()
    def list_suppressed(days: int = 30) -> str:
        """Offers that matched rules but were suppressed, with reason."""
        return queries.dumps(queries.list_suppressed(db, days=days))

    @mcp.tool()
    def parse_stats(days: int = 30) -> str:
        """Raw message status counts (triage/parse rates)."""
        return queries.dumps(queries.parse_stats(db, days=days))

    @mcp.tool()
    def catalog_lookup(query: str) -> str:
        """Resolve free text to a catalog model_key."""
        hit = queries.catalog_lookup(query)
        return queries.dumps(hit or {"error": "not_found", "query": query})

    @mcp.tool()
    def simulate_rules(days: int = 90) -> str:
        """Replay offers against current config watch rules."""
        from garimpo.settings import load_settings
        from garimpo.tools.simulate import simulate

        settings = load_settings()
        settings.storage.path = db
        report = simulate(settings, days=days)
        return queries.dumps(
            {"days": report.days, "offers": report.offers, "by_level": report.by_level}
        )

    mcp.run()


if __name__ == "__main__":
    main()

"""MCP query helpers / export tests."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from garimpo.mcp import queries
from garimpo.store.db import connect
from garimpo.store.repo import history as history_repo


def test_query_and_export(tmp_path: Path) -> None:
    db = tmp_path / "q.db"
    conn = connect(db)
    history_repo.insert_history(
        conn,
        model_key="rtx_5070_ti",
        price=5799.0,
        observed_at=datetime(2026, 6, 1),
        origin="backfill",
        store="kabum",
    )
    history_repo.insert_history(
        conn,
        model_key="rtx_5070_ti",
        price=5600.0,
        observed_at=datetime(2026, 7, 1),
        origin="backfill",
        store="kabum",
    )
    conn.close()

    hist = queries.query_price_history(db, "rtx_5070_ti", days=365)
    assert hist["n"] == 2
    assert hist["min"] == 5600.0

    out = tmp_path / "out.csv"
    n = queries.export_price_history_csv(db, out)
    assert n == 2
    assert out.is_file()


def test_catalog_lookup() -> None:
    hit = queries.catalog_lookup("RTX 5070 Ti ASUS")
    assert hit is not None
    assert hit["model_key"] == "rtx_5070_ti"

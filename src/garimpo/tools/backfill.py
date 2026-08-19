"""CSV backfill into price_history.

CSV columns: model_key,price,store,observed_at[,condition]
"""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

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

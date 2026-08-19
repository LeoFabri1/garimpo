"""Load versioned catalog JSON into in-memory structures."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from garimpo.models.catalog import Catalog, CatalogMeta, Product


def default_catalog_dir() -> Path:
    """Resolve catalog directory (repo checkout, cwd, or packaged wheel data)."""
    env = os.environ.get("GARIMPO_CATALOG_DIR")
    candidates: list[Path] = []
    if env:
        candidates.append(Path(env))
    candidates.extend(
        [
            Path.cwd() / "catalog",
            Path(__file__).resolve().parents[3] / "catalog",  # repo root from src/
            Path(__file__).resolve().parent / "data" / "catalog",  # wheel force-include
        ]
    )
    for path in candidates:
        if (path / "gpu.json").is_file():
            return path
    return candidates[0]


def load_gpu_catalog(path: Path | None = None) -> Catalog:
    catalog_path = path or (default_catalog_dir() / "gpu.json")
    raw: dict[str, Any] = json.loads(catalog_path.read_text(encoding="utf-8"))
    meta_raw = raw["meta"]
    meta = CatalogMeta(
        perf_basis=meta_raw["perf_basis"],
        perf_reference=meta_raw["perf_reference"],
        updated_at=meta_raw["updated_at"],
    )
    products: dict[str, Product] = {}
    for key, item in raw["products"].items():
        price_range = item.get("price_range")
        products[key] = Product(
            key=key,
            display=item["display"],
            vendor=item["vendor"],
            perf=float(item["perf"]),
            aliases=tuple(a.lower() for a in item["aliases"]),
            negative_aliases=tuple(a.lower() for a in item.get("negative_aliases", [])),
            vram_gb=item.get("vram_gb"),
            generation=item.get("generation"),
            msrp_brl=item.get("msrp_brl"),
            price_range=tuple(price_range) if price_range else None,
        )
    return Catalog(meta=meta, products=products)


def load_stores(path: Path | None = None) -> dict[str, dict[str, Any]]:
    stores_path = path or (default_catalog_dir() / "stores.json")
    return json.loads(stores_path.read_text(encoding="utf-8"))

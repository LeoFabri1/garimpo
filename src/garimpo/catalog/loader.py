"""Load versioned catalog JSON into in-memory structures."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from garimpo.models.catalog import Catalog, CatalogMeta, Product


class CatalogNotFoundError(FileNotFoundError):
    """No catalog directory on the search path — usually a broken install."""


def catalog_dir_candidates() -> list[Path]:
    """Search order: explicit env, local override, repo checkout, packaged data."""
    candidates: list[Path] = []
    env = os.environ.get("GARIMPO_CATALOG_DIR")
    if env:
        candidates.append(Path(env))
    here = Path(__file__).resolve()
    candidates.extend(
        [
            Path.cwd() / "catalog",
            here.parents[3] / "catalog",  # repo root, from src/garimpo/catalog/
            here.parents[1] / "data" / "catalog",  # installed wheel force-include
        ]
    )
    return candidates


def default_catalog_dir() -> Path:
    """Resolve the catalog directory, or explain every path that was tried."""
    candidates = catalog_dir_candidates()
    for path in candidates:
        if (path / "gpu.json").is_file():
            return path
    tried = "\n".join(f"  • {p}" for p in candidates)
    raise CatalogNotFoundError(
        "Catálogo não encontrado. Procurei em:\n"
        f"{tried}\n"
        "Defina GARIMPO_CATALOG_DIR ou rode a partir de um checkout do repo."
    )


def load_catalog_file(path: Path) -> Catalog:
    raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
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


def load_gpu_catalog(path: Path | None = None) -> Catalog:
    catalog_path = path or (default_catalog_dir() / "gpu.json")
    return load_catalog_file(catalog_path)


def load_category_catalog(category: str) -> Catalog:
    path = default_catalog_dir() / "categories" / f"{category}.json"
    return load_catalog_file(path)


def merge_catalogs(*catalogs: Catalog) -> Catalog:
    """Merge products; first catalog wins on key collision for meta."""
    if not catalogs:
        raise ValueError("merge_catalogs requires at least one catalog")
    products: dict[str, Product] = {}
    for cat in catalogs:
        for key, product in cat.products.items():
            if key not in products:
                products[key] = product
    return Catalog(meta=catalogs[0].meta, products=products)


def load_catalog_for_watch(categories: list[str] | None = None) -> Catalog:
    """GPU always loaded; optional category files merged for multi-category watch."""
    base = load_gpu_catalog()
    if not categories:
        return base
    extra: list[Catalog] = []
    for cat in categories:
        if cat in {"gpu", ""}:
            continue
        path = default_catalog_dir() / "categories" / f"{cat}.json"
        if path.is_file():
            extra.append(load_catalog_file(path))
    if not extra:
        return base
    return merge_catalogs(base, *extra)


def load_stores(path: Path | None = None) -> dict[str, dict[str, Any]]:
    stores_path = path or (default_catalog_dir() / "stores.json")
    return json.loads(stores_path.read_text(encoding="utf-8"))

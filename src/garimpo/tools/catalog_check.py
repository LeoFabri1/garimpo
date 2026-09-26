"""Validate catalog JSON: duplicate aliases, collisions, required fields."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from garimpo.catalog.loader import (
    CatalogNotFoundError,
    default_catalog_dir,
    load_catalog_file,
)
from garimpo.models.catalog import Product


def check_catalogs(catalog_dir: Path | None = None) -> list[str]:
    try:
        root = catalog_dir or default_catalog_dir()
    except CatalogNotFoundError as exc:
        return [str(exc)]
    errors: list[str] = []
    paths = [root / "gpu.json"]
    categories = root / "categories"
    if categories.is_dir():
        paths.extend(sorted(categories.glob("*.json")))

    alias_owners: dict[str, list[str]] = defaultdict(list)
    products_by_owner: dict[str, Product] = {}
    for path in paths:
        if not path.is_file():
            errors.append(f"missing: {path}")
            continue
        try:
            catalog = load_catalog_file(path)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{path.name}: {exc}")
            continue
        for key, product in catalog.products.items():
            if not product.aliases:
                errors.append(f"{path.name}:{key}: aliases vazio")
            if product.perf <= 0:
                errors.append(f"{path.name}:{key}: perf deve ser > 0")
            owner = f"{path.name}:{key}"
            products_by_owner[owner] = product
            for alias in product.aliases:
                alias_owners[alias].append(owner)
            for neg in product.negative_aliases:
                if neg in product.aliases:
                    errors.append(
                        f"{path.name}:{key}: negative_alias {neg!r} também é alias"
                    )
            for req in product.required_aliases:
                if req in product.negative_aliases:
                    errors.append(
                        f"{path.name}:{key}: required_alias {req!r} também é negative"
                    )

    for alias, owners in sorted(alias_owners.items()):
        if len(owners) > 1 and not _mutually_exclusive(owners, products_by_owner):
            errors.append(f"alias duplicado {alias!r} → {', '.join(owners)}")

    return errors


def _mutually_exclusive(owners: list[str], by_owner: dict[str, Product]) -> bool:
    """Two products may share an alias when they can never match the same text.

    "rtx 4060" is honestly the name of both the desktop card and the notebook
    GPU; only the word "notebook" tells them apart. That is not the ambiguity
    this check exists to catch, so it is allowed — but only when the catalog
    proves the split: every token one product requires must be a negative of
    the other. `required_aliases` is an OR, so a single token left uncovered
    would be enough to let both answer the same ad.
    """
    for a in owners:
        for b in owners:
            if a is b:
                continue
            pa, pb = by_owner.get(a), by_owner.get(b)
            if pa is None or pb is None:
                return False
            split = (
                pa.required_aliases
                and set(pa.required_aliases) <= set(pb.negative_aliases)
            ) or (
                pb.required_aliases
                and set(pb.required_aliases) <= set(pa.negative_aliases)
            )
            if not split:
                return False
    return True

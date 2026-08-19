"""Validate catalog JSON: duplicate aliases, collisions, required fields."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from garimpo.catalog.loader import default_catalog_dir, load_catalog_file


def check_catalogs(catalog_dir: Path | None = None) -> list[str]:
    root = catalog_dir or default_catalog_dir()
    errors: list[str] = []
    paths = [root / "gpu.json"]
    categories = root / "categories"
    if categories.is_dir():
        paths.extend(sorted(categories.glob("*.json")))

    alias_owners: dict[str, list[str]] = defaultdict(list)
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
            for alias in product.aliases:
                alias_owners[alias].append(f"{path.name}:{key}")
            for neg in product.negative_aliases:
                if neg in product.aliases:
                    errors.append(
                        f"{path.name}:{key}: negative_alias {neg!r} também é alias"
                    )

    for alias, owners in sorted(alias_owners.items()):
        if len(owners) > 1:
            errors.append(f"alias duplicado {alias!r} → {', '.join(owners)}")

    return errors

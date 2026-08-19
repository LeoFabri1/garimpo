"""R$ per performance point."""

from __future__ import annotations

from decimal import Decimal

from garimpo.models.catalog import Product


def price_per_perf(price: Decimal | float, product: Product) -> float | None:
    if product.perf <= 0:
        return None
    return float(price) / float(product.perf)

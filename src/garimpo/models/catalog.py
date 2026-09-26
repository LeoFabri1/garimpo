"""Catalog product definitions."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Product:
    key: str
    display: str
    vendor: str
    perf: float
    aliases: tuple[str, ...]
    negative_aliases: tuple[str, ...] = ()
    # At least one of these must appear anywhere in the text, or the product
    # cannot answer. Lets an alias carry only the model name while the class
    # token ("notebook") is demanded separately, however far away it sits.
    required_aliases: tuple[str, ...] = ()
    vram_gb: int | None = None
    generation: str | None = None
    msrp_brl: float | None = None
    price_range: tuple[float, float] | None = None


@dataclass(frozen=True, slots=True)
class CatalogMeta:
    perf_basis: str
    perf_reference: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class Catalog:
    meta: CatalogMeta
    products: dict[str, Product] = field(default_factory=dict)

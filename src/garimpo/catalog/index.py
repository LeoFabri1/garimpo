"""Inverted alias index: longest alias first, negative_aliases as safety net."""

from __future__ import annotations

from dataclasses import dataclass

from rapidfuzz import fuzz, process

from garimpo.models.catalog import Catalog, Product


@dataclass(frozen=True, slots=True)
class ResolveResult:
    model_key: str
    confidence: float
    matched_alias: str | None
    method: str  # exact | fuzzy


class ModelIndex:
    def __init__(self, catalog: Catalog) -> None:
        self._catalog = catalog
        pairs: list[tuple[str, str]] = []
        for key, product in catalog.products.items():
            for alias in product.aliases:
                pairs.append((alias, key))
        pairs.sort(key=lambda p: len(p[0]), reverse=True)
        self._pairs = pairs
        self._alias_list = [a for a, _ in pairs]

    def get(self, model_key: str) -> Product | None:
        return self._catalog.products.get(model_key)

    def resolve(self, text: str, *, fuzzy_cutoff: int = 88) -> ResolveResult | None:
        lowered = text.lower()

        for alias, key in self._pairs:
            if alias not in lowered:
                continue
            product = self._catalog.products[key]
            if _hits_negative(lowered, alias, product.negative_aliases):
                continue
            return ResolveResult(
                model_key=key,
                confidence=1.0,
                matched_alias=alias,
                method="exact",
            )

        if not self._alias_list:
            return None

        match = process.extractOne(
            lowered,
            self._alias_list,
            scorer=fuzz.partial_ratio,
            score_cutoff=fuzzy_cutoff,
        )
        if match is None:
            return None
        alias, score, _idx = match
        key = next(k for a, k in self._pairs if a == alias)
        product = self._catalog.products[key]
        if _hits_negative(lowered, alias, product.negative_aliases):
            return None
        return ResolveResult(
            model_key=key,
            confidence=float(score) / 100.0,
            matched_alias=alias,
            method="fuzzy",
        )


def _hits_negative(text: str, matched_alias: str, negatives: tuple[str, ...]) -> bool:
    for neg in negatives:
        if neg == matched_alias:
            return True
        # More specific form present → this product is the wrong one
        if neg in text and len(neg) > len(matched_alias):
            return True
    return False

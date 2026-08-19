"""Generic regex heuristics for Brazilian GPU deal messages."""

from __future__ import annotations

import re
from decimal import Decimal

from garimpo.catalog.index import ModelIndex
from garimpo.models.offer import Offer, Price
from garimpo.models.raw import RawMessage
from garimpo.parse.money import MoneyParseError, select_price
from garimpo.parse.text import normalize_text
from garimpo.parse.triage import passes_triage

_BRANDS = (
    "asus",
    "msi",
    "gigabyte",
    "zotac",
    "pny",
    "galax",
    "xfx",
    "sapphire",
    "powercolor",
    "inno3d",
    "palit",
    "gainward",
    "colorful",
    "asrock",
    "biostar",
    "evga",
    "acer",
    "lenovo",
    "dell",
    "hp",
    "samsung",
    "avell",
)

_STORES = (
    ("kabum", re.compile(r"\bkabum\b", re.I)),
    ("terabyte", re.compile(r"\bterabyte\b", re.I)),
    ("pichau", re.compile(r"\bpichau\b", re.I)),
    ("amazon", re.compile(r"\bamazon\b|\bamzn\b", re.I)),
    ("magalu", re.compile(r"\b(magalu|magazine\s*luiza|magazine\s*você)\b", re.I)),
    ("americanas", re.compile(r"\bamericanas\b", re.I)),
    ("aliexpress", re.compile(r"\baliexpress\b", re.I)),
    ("gkef", re.compile(r"\b(gk\s*info|gkinfostore)\b", re.I)),
    ("marketplace_generico", re.compile(r"\b(mercado\s*livre|shopee)\b", re.I)),
)

_PIX = re.compile(r"\b(pix|à\s*vista|a\s*vista)\b", re.I)


class GenericParser:
    name = "generic"

    def __init__(self, index: ModelIndex) -> None:
        self._index = index

    def can_handle(self, msg: RawMessage) -> bool:
        return bool(msg.text)

    def parse(self, msg: RawMessage) -> Offer | None:
        if not msg.text:
            return None
        if not passes_triage(msg.text):
            return None

        cleaned = normalize_text(msg.text)
        resolved = self._index.resolve(cleaned)
        if resolved is None:
            return None

        product = self._index.get(resolved.model_key)
        assert product is not None

        try:
            amount, listed = select_price(cleaned, price_range=product.price_range)
        except MoneyParseError:
            return None

        confidence = resolved.confidence
        if product.msrp_brl is not None:
            msrp = Decimal(str(product.msrp_brl))
            if amount < msrp * Decimal("0.3") or amount > msrp * Decimal("2.0"):
                confidence = min(confidence, 0.5)
        elif product.price_range is not None:
            lo, hi = product.price_range
            if float(amount) < lo * 0.5 or float(amount) > hi * 1.2:
                confidence = min(confidence, 0.5)

        brand = _find_brand(cleaned)
        store = _find_store(cleaned)
        method = "pix" if _PIX.search(cleaned) else "unknown"

        return Offer(
            model_key=resolved.model_key,
            price=Price(
                amount=amount,
                method=method,  # type: ignore[arg-type]
                listed=listed,
            ),
            brand=brand,
            store=store,
            extracted_by="regex",
            confidence=confidence,
        )


def _find_brand(text: str) -> str | None:
    lowered = text.lower()
    for brand in _BRANDS:
        if brand in lowered:
            return brand.upper() if brand != "asus" else "ASUS"
    return None


def _find_store(text: str) -> str | None:
    for key, pattern in _STORES:
        if pattern.search(text):
            return key
    return None

"""Generic regex heuristics for Brazilian GPU deal messages."""

from __future__ import annotations

import re
from decimal import Decimal

from garimpo.catalog.index import ModelIndex
from garimpo.models.offer import Offer, Price
from garimpo.models.raw import RawMessage
from garimpo.parse.enrich import enrich_offer, extract_purchase_url
from garimpo.parse.money import MoneyParseError, select_price
from garimpo.parse.text import normalize_text
from garimpo.parse.triage import CATEGORY_TRIAGE, offer_body, passes_triage

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

# Host in the product URL beats free-text shop names in commentary.
_STORE_HOSTS = (
    ("kabum", re.compile(r"kabum\.com\.br", re.I)),
    ("terabyte", re.compile(r"terabyteshop\.com\.br", re.I)),
    ("pichau", re.compile(r"pichau\.com\.br", re.I)),
    ("amazon", re.compile(r"amazon\.com\.br|\bamzn\.to\b|\blink\.amazon\b", re.I)),
    (
        "magalu",
        re.compile(r"magazineluiza\.com\.br|magazinevoce\.com\.br|divulgadormagalu\.com", re.I),
    ),
    ("americanas", re.compile(r"americanas\.com\.br", re.I)),
    ("aliexpress", re.compile(r"aliexpress\.com", re.I)),
    (
        "marketplace_generico",
        re.compile(r"mercadolivre\.com\.br|\bmeli\.la\b|shopee\.com\.br", re.I),
    ),
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
        # All categories here: the pipeline already gated on the watched ones,
        # and the catalog only holds products of those categories anyway.
        if not passes_triage(msg.text, CATEGORY_TRIAGE):
            return None

        # Resolve against the product block only (everything before the first
        # URL). Channel footers compare against other SKUs ("28% cheaper than
        # the 9070 XT") and name other shops ("like the terabyte one above");
        # matching the full message used to steal the model and the store.
        body = normalize_text(offer_body(msg.text))
        resolved = self._index.resolve(body)
        if resolved is None:
            return None

        product = self._index.get(resolved.model_key)
        assert product is not None

        try:
            # Line breaks kept: they are what separates a model's "3X" from
            # the price on the next line (see money._INSTALLMENT).
            price_text = "\n".join(
                normalize_text(line) for line in offer_body(msg.text).splitlines()
            )
            amount, listed = select_price(price_text, price_range=product.price_range)
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

        brand = _find_brand(body)
        # The purchase link's host first: a coupon or footer link elsewhere in
        # the message can point at a different shop.
        store = (
            _find_store(body)
            or _find_store_host(extract_purchase_url(msg.text) or "")
            or _find_store_host(msg.text)
        )
        method = "pix" if _PIX.search(body) else "unknown"

        offer = Offer(
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
        # Coupon often sits in the product block, and the purchase link is not
        # necessarily the first one (see parse/enrich.py). Read both from the
        # raw text.
        return enrich_offer(offer, msg.text)


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


def _find_store_host(text: str) -> str | None:
    for key, pattern in _STORE_HOSTS:
        if pattern.search(text):
            return key
    return None

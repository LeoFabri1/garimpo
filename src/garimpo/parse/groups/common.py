"""Shared preprocessing for group-specific Telegram deal formats."""

from __future__ import annotations

import re

from garimpo.models.offer import Coupon, Offer

_BBCODE = re.compile(r"\[/?[^\]]+\]")
_COUPON = re.compile(
    r"(?:cupom|coupon|c[oó]digo)\s*[:=\-]?\s*([A-Za-z0-9_-]{3,24})",
    re.IGNORECASE,
)
# Bare "Preço: 5.799,00" / "Valor PIX 5799" without R$
_BARE_PRICE_LABEL = re.compile(
    r"\b(pre[cç]o|valor|por)\s*(?:pix|avista|à\s*vista|a\s*vista)?\s*[:=]?\s*"
    r"(?!R\$)(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?|\d{4,6})\b",
    re.IGNORECASE,
)
_PELANDO_TEMP = re.compile(r"\b\d{1,3}\s*°\b")


def strip_bbcode(text: str) -> str:
    return _BBCODE.sub(" ", text)


def strip_pelando_noise(text: str) -> str:
    return _PELANDO_TEMP.sub(" ", text)


def ensure_currency_markers(text: str) -> str:
    """Insert R$ after price labels so the money parser can see amounts."""

    def _repl(match: re.Match[str]) -> str:
        label = match.group(1)
        amount = match.group(2)
        return f"{label}: R$ {amount}"

    return _BARE_PRICE_LABEL.sub(_repl, text)


def extract_coupon_code(text: str) -> str | None:
    match = _COUPON.search(text)
    if match is None:
        return None
    return match.group(1).upper()


def with_coupon(offer: Offer | None, text: str) -> Offer | None:
    if offer is None:
        return None
    if offer.coupon is not None and offer.coupon.code:
        return offer
    code = extract_coupon_code(text)
    if not code:
        return offer
    return Offer(
        model_key=offer.model_key,
        price=offer.price,
        brand=offer.brand,
        variant=offer.variant,
        condition=offer.condition,
        coupon=Coupon(code=code),
        store=offer.store,
        url=offer.url,
        extracted_by=offer.extracted_by,
        confidence=offer.confidence,
    )

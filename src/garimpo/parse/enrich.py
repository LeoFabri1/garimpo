"""Attach coupon / purchase URL onto a parsed Offer."""

from __future__ import annotations

import re

from garimpo.models.offer import Coupon, Offer

_COUPON = re.compile(
    r"(?:cupom|coupon|c[oó]digo)\s*[:=\-]?\s*([A-Za-z0-9_-]{3,24})",
    re.IGNORECASE,
)
# First http(s) URL — by convention the purchase link sits before channel footers.
_URL = re.compile(r"https?://[^\s<>\"'\]]+", re.IGNORECASE)


def extract_coupon_code(text: str) -> str | None:
    match = _COUPON.search(text)
    if match is None:
        return None
    return match.group(1).upper()


def extract_first_url(text: str) -> str | None:
    match = _URL.search(text)
    if match is None:
        return None
    return match.group(0).rstrip(").,;!?")


def enrich_offer(offer: Offer | None, text: str) -> Offer | None:
    """Attach coupon code and purchase URL from the raw message text."""
    if offer is None:
        return None
    code = offer.coupon.code if offer.coupon and offer.coupon.code else extract_coupon_code(text)
    url = offer.url or extract_first_url(text)
    if code == (offer.coupon.code if offer.coupon else None) and url == offer.url:
        return offer
    return Offer(
        model_key=offer.model_key,
        price=offer.price,
        brand=offer.brand,
        variant=offer.variant,
        condition=offer.condition,
        coupon=Coupon(code=code) if code else offer.coupon,
        store=offer.store,
        url=url,
        extracted_by=offer.extracted_by,
        confidence=offer.confidence,
    )

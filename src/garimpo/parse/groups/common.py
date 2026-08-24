"""Shared preprocessing for group-specific Telegram deal formats."""

from __future__ import annotations

import re

from garimpo.models.offer import Offer
from garimpo.parse.enrich import (
    enrich_offer,
    extract_coupon_code,
    extract_first_url,
)

_BBCODE = re.compile(r"\[/?[^\]]+\]")
# Bare "Preço: 5.799,00" / "Valor PIX 5799" without R$
_BARE_PRICE_LABEL = re.compile(
    r"\b(pre[cç]o|valor|por)\s*(?:pix|avista|à\s*vista|a\s*vista)?\s*[:=]?\s*"
    r"(?!R\$)(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?|\d{4,6})\b",
    re.IGNORECASE,
)
_PELANDO_TEMP = re.compile(r"\b\d{1,3}\s*°\b")

__all__ = [
    "enrich_offer",
    "ensure_currency_markers",
    "extract_coupon_code",
    "extract_first_url",
    "strip_bbcode",
    "strip_pelando_noise",
    "with_coupon",
]


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


def with_coupon(offer: Offer | None, text: str) -> Offer | None:
    """Back-compat alias — prefer enrich_offer."""
    return enrich_offer(offer, text)

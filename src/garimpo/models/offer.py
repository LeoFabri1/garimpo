"""Structured offer extracted from a message."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

PriceMethod = Literal["pix", "boleto", "card", "unknown"]
Condition = Literal["new", "used", "refurb"]
ExtractedBy = Literal["regex", "llm"]


@dataclass(frozen=True, slots=True)
class Coupon:
    code: str | None
    discount_abs: Decimal | None = None
    discount_pct: Decimal | None = None


@dataclass(frozen=True, slots=True)
class Price:
    amount: Decimal
    method: PriceMethod = "unknown"
    listed: Decimal | None = None
    installments: int | None = None


@dataclass(frozen=True, slots=True)
class Offer:
    model_key: str
    price: Price
    brand: str | None = None
    variant: str | None = None
    condition: Condition = "new"
    coupon: Coupon | None = None
    store: str | None = None
    url: str | None = None
    extracted_by: ExtractedBy = "regex"
    confidence: float = 1.0

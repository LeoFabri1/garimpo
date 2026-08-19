"""LLM provider Protocol — extraction only, never alert decisions (P3)."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal, Protocol

from pydantic import BaseModel


class ExtractedOffer(BaseModel):
    is_gpu: bool
    model_raw: str | None = None
    brand: str | None = None
    price: Decimal | None = None
    price_method: Literal["pix", "boleto", "card", "unknown"] = "unknown"
    coupon: str | None = None
    store: str | None = None
    condition: Literal["new", "used", "refurb"] = "new"
    confidence: Literal["high", "medium", "low"] = "medium"


class LLMProvider(Protocol):
    async def extract(self, text: str) -> ExtractedOffer | None: ...

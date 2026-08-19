"""Brazilian currency parsing — highest silent-bug surface in the project."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

# Prefer amounts with currency markers so model numbers (5070, 9070) are ignored.
_AMOUNT_BRL = re.compile(
    r"R\$\s*(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?|\d+(?:[.,]\d{2})?)",
    re.IGNORECASE,
)
_AMOUNT_REAIS = re.compile(
    r"(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?|\d+(?:[.,]\d{2})?)\s*reais?\b",
    re.IGNORECASE,
)

_INSTALLMENT = re.compile(
    r"(\d{1,2})\s*[xX×]\s*(?:de\s+)?(?:R\$\s*)?([\d.,]+)",
    re.IGNORECASE,
)

_PRIORITY_NEAR = re.compile(
    r"(?:por|à\s*vista|a\s*vista|no\s*pix|pix|final|agora)\s*:?\s*"
    r"(?:R\$\s*)?([\d.,]+)",
    re.IGNORECASE,
)

_DE_POR = re.compile(
    r"de\s*(?:R\$\s*)?([\d.,]+)\s*por\s*(?:R\$\s*)?([\d.,]+)",
    re.IGNORECASE,
)


class MoneyParseError(ValueError):
    pass


def parse_brl(s: str) -> Decimal:
    """Parse a single BRL amount string into Decimal.

    Handles BR (`5.799,00`), bare (`5799`), and infiltrated US (`5,799.00`).
    """
    raw = s.strip()
    if not raw:
        raise MoneyParseError("empty amount")

    cleaned = re.sub(r"^\s*R\$\s*", "", raw, flags=re.IGNORECASE)
    cleaned = cleaned.strip()
    cleaned = re.sub(r"\s*(reais|real)\s*$", "", cleaned, flags=re.IGNORECASE).strip()

    if not cleaned:
        raise MoneyParseError(f"unparseable amount: {s!r}")

    try:
        if "," in cleaned and "." in cleaned:
            if cleaned.rindex(",") > cleaned.rindex("."):
                normalized = cleaned.replace(".", "").replace(",", ".")
            else:
                normalized = cleaned.replace(",", "")
        elif "," in cleaned:
            frac = cleaned.split(",")[-1]
            if len(frac) == 2 and frac.isdigit():
                normalized = cleaned.replace(",", ".")
            else:
                normalized = cleaned.replace(",", "")
        elif "." in cleaned:
            frac = cleaned.split(".")[-1]
            if len(frac) == 3 and frac.isdigit():
                normalized = cleaned.replace(".", "")
            else:
                normalized = cleaned
        else:
            normalized = cleaned

        value = Decimal(normalized)
    except (InvalidOperation, ValueError) as exc:
        raise MoneyParseError(f"unparseable amount: {s!r}") from exc

    if value < 0:
        raise MoneyParseError(f"negative amount: {s!r}")
    return value


def _extract_installment_amounts(text: str) -> set[Decimal]:
    out: set[Decimal] = set()
    for match in _INSTALLMENT.finditer(text):
        try:
            out.add(parse_brl(match.group(2)))
        except MoneyParseError:
            continue
    return out


def _currency_amounts(text: str) -> list[Decimal]:
    found: list[Decimal] = []
    for pattern in (_AMOUNT_BRL, _AMOUNT_REAIS):
        for match in pattern.finditer(text):
            try:
                found.append(parse_brl(match.group(1)))
            except MoneyParseError:
                continue
    return found


def select_price(
    text: str,
    *,
    price_range: tuple[float, float] | None = None,
) -> tuple[Decimal, Decimal | None]:
    """Pick cash/PIX price from message text.

    Returns `(price, price_listed)`.
    Prefers PIX/à-vista over installment totals, and rejects values outside
    the product's plausible range.
    """
    de_por = _DE_POR.search(text)
    if de_por:
        listed = parse_brl(de_por.group(1))
        price = parse_brl(de_por.group(2))
        return price, listed

    installment_vals = _extract_installment_amounts(text)

    priority: list[Decimal] = []
    for match in _PRIORITY_NEAR.finditer(text):
        try:
            val = parse_brl(match.group(1))
        except MoneyParseError:
            continue
        if val not in installment_vals:
            priority.append(val)

    candidates = [v for v in _currency_amounts(text) if v not in installment_vals]

    pool = priority or candidates
    if not pool:
        raise MoneyParseError("no price found")

    if price_range is not None:
        lo, hi = Decimal(str(price_range[0])), Decimal(str(price_range[1]))
        in_range = [p for p in pool if lo <= p <= hi]
        if in_range:
            return min(in_range), None

    return min(pool), None

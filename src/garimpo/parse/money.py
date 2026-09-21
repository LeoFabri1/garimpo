"""Brazilian currency parsing — highest silent-bug surface in the project."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

# Number forms, longest-first. Alternation in `re` is ordered: a shorter branch
# that matches wins outright, so a bare four-digit amount must not be offered a
# three-digit branch first. `\d{1,3}` used to swallow "219" out of "2199,00" and
# the amount silently became a tenth of the real price.
_NUM = (
    r"\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?"  # BR grouped: 1.234.567,89
    r"|\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?"  # US grouped: 1,234,567.89
    r"|\d+(?:[.,]\d{1,2})?"  # bare: 5799 / 2199,00 / 899.90
)

# Prefer amounts with currency markers so model numbers (5070, 9070) are ignored.
_AMOUNT_BRL = re.compile(rf"R\$\s*({_NUM})", re.IGNORECASE)
_AMOUNT_REAIS = re.compile(rf"({_NUM})\s*reais?\b", re.IGNORECASE)

# Same line only: "MSI RTX 5070 Ti SHADOW 3X" followed by the price on the next
# line is a fan count, not "3x de R$ 6.991".
_INSTALLMENT = re.compile(
    r"(\d{1,2})[^\S\n]*[xX×][^\S\n]*(?:de[^\S\n]+)?(?:R\$[^\S\n]*)?([\d.,]+)",
    re.IGNORECASE,
)

# "no pix: R$ 2.199" — keyword announces the amount.
_PRIORITY_BEFORE = re.compile(
    rf"(?:por|à\s*vista|a\s*vista|no\s*pix|pix|final|agora)\s*:?\s*"
    rf"(?:R\$\s*)?({_NUM})",
    re.IGNORECASE,
)

# "R$ 2.199,00 no pix" — the far more common order in real deal messages, and
# invisible to a forward-only pattern.
_PRIORITY_AFTER = re.compile(
    rf"(?:R\$\s*)?({_NUM})\s*(?:no\s*pix|à\s*vista|a\s*vista|no\s*boleto)",
    re.IGNORECASE,
)

# A coupon or discount is not the price. "Resgate o cupom de R$90 OFF" on a
# 5070 Ti otherwise made the card cost ninety reais.
_DISCOUNT = re.compile(
    rf"(?:cupom|desconto)[^\n]{{0,40}}?R\$\s*({_NUM})"
    rf"|R\$\s*({_NUM})\s*(?:de\s+)?(?:off|de\s+desconto)",
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
            # One or two digits is a decimal ("2199,0"); three is US thousands.
            if len(frac) in (1, 2) and frac.isdigit():
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


def _discount_amounts(text: str) -> set[Decimal]:
    """Amounts announced as coupon/discount — never the price itself."""
    out: set[Decimal] = set()
    for match in _DISCOUNT.finditer(text):
        raw = match.group(1) or match.group(2)
        if raw is None:
            continue
        try:
            out.add(parse_brl(raw))
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

    ignore = _extract_installment_amounts(text) | _discount_amounts(text)

    priority: list[Decimal] = []
    for pattern in (_PRIORITY_BEFORE, _PRIORITY_AFTER):
        for match in pattern.finditer(text):
            try:
                val = parse_brl(match.group(1))
            except MoneyParseError:
                continue
            if val not in ignore:
                priority.append(val)

    candidates = [v for v in _currency_amounts(text) if v not in ignore]

    pool = priority or candidates
    if not pool:
        raise MoneyParseError("no price found")

    if price_range is not None:
        lo, hi = Decimal(str(price_range[0])), Decimal(str(price_range[1]))
        in_range = [p for p in pool if lo <= p <= hi]
        # A gate, not a hint. Returning an out-of-range amount stored a price
        # that was silently a tenth of the real one; no offer beats a wrong one.
        if not in_range:
            raise MoneyParseError(f"nenhum preço plausível em {lo}–{hi}: {sorted(pool)}")
        return min(in_range), None

    return min(pool), None

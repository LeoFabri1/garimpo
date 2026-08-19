"""Unit tests for Brazilian money parsing."""

from __future__ import annotations

from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from garimpo.parse.money import MoneyParseError, parse_brl, select_price


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("R$ 5.799,00", "5799.00"),
        ("R$ 5.799", "5799"),
        ("R$5799,90", "5799.90"),
        ("5.799 reais", "5799"),
        ("R$ 5,799.00", "5799.00"),
        ("5799", "5799"),
        ("1.234.567,89", "1234567.89"),
    ],
)
def test_parse_brl_examples(raw: str, expected: str) -> None:
    assert parse_brl(raw) == Decimal(expected)


def test_parse_brl_rejects_empty() -> None:
    with pytest.raises(MoneyParseError):
        parse_brl("")


@given(st.decimals(min_value=1, max_value=99_999, places=2, allow_nan=False, allow_infinity=False))
def test_parse_brl_roundtrip_br_format(value: Decimal) -> None:
    # Format as BR: thousands with dot, decimals with comma
    quantized = value.quantize(Decimal("0.01"))
    int_part = int(quantized)
    cents = int((quantized - int_part) * 100)
    br = f"{int_part:,}".replace(",", ".") + f",{cents:02d}"
    assert parse_brl(br) == quantized
    assert parse_brl(f"R$ {br}") == quantized


def test_select_price_de_por() -> None:
    price, listed = select_price("de R$ 6.899 por R$ 5.799")
    assert price == Decimal("5799")
    assert listed == Decimal("6899")


def test_select_price_ignores_installments() -> None:
    text = "RTX 5070 Ti 12x R$ 483,25 ou R$ 5.799 no PIX"
    price, _ = select_price(text, price_range=(3000, 12000))
    assert price == Decimal("5799")


def test_select_price_prefers_pix_phrase() -> None:
    text = "RTX 5070 Ti de R$ 6500 no cartão / R$ 5.799 no PIX"
    price, _ = select_price(text, price_range=(3000, 12000))
    assert price == Decimal("5799")

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


# --- Regressions from real @iskandarsouza traffic (2026-08) -----------------
# Every case below was silently mis-parsed in production: 50 of 166 stored
# offers landed outside the catalog band, all of them a tenth of the real
# price, because `\d{1,3}` won the alternation and truncated the amount.


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("R$ 1999,00", "1999.00"),
        ("R$ 2020", "2020"),
        ("R$ 2089,05", "2089.05"),
        ("R$ 2112", "2112"),
        ("R$ 2180,68", "2180.68"),
        ("R$ 12999,00", "12999.00"),
        ("R$ 5799", "5799"),
    ],
)
def test_four_digit_amount_without_separator(raw: str, expected: str) -> None:
    """A bare four-digit amount must not be truncated to three digits."""
    price, _ = select_price(f"Placa de Video RTX 5060\nValor: {raw}")
    assert price == Decimal(expected)


def test_pix_keyword_after_the_amount() -> None:
    """Real messages write the amount first: 'R$ 2199,00 no pix'."""
    text = "Placa De Video Msi Geforce Rtx 5060 Cyclone Oc\nValor : R$ 2199,00  No pix"
    price, _ = select_price(text, price_range=(1500, 5000))
    assert price == Decimal("2199.00")


def test_coupon_amount_is_not_the_price() -> None:
    """'Resgate o cupom de R$90 OFF' made a 5070 Ti cost ninety reais."""
    text = "Placa de Vídeo MSI RTX 5070 TI 16GB\nResgate o cupom de R$90 OFF"
    with pytest.raises(MoneyParseError):
        select_price(text, price_range=(3000, 12000))


def test_coupon_does_not_shadow_a_real_price() -> None:
    text = "RTX 5060 Shadow 2X OC\nValor: R$ 2020\nCupom: F3L1Z200"
    price, _ = select_price(text, price_range=(1500, 5000))
    assert price == Decimal("2020")


def test_out_of_range_is_a_gate_not_a_hint() -> None:
    """No offer beats a wrong one — an implausible price must not be returned."""
    with pytest.raises(MoneyParseError):
        select_price("RTX 5090 por R$ 1727", price_range=(12000, 28000))

"""Purchase URL and coupon, read from the shapes the watched channels post.

Links are example.com stand-ins for the shorteners in the real messages.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from garimpo.parse.enrich import extract_coupon, extract_purchase_url

# Shopee via a channel: the FIRST link redeems the coupon, the product is second.
COUPON_LINK_FIRST = (
    "O preço vai subir, hein?!\n\n"
    "Placa de Vídeo NVIDIA GeForce MSI RTX5060 8GB por R$2.142,68\n"
    "🎟️Com cupom de R$100 OFF da Shopee\n\n"
    "Resgate o cupom: https://cupom.example.com/a\n\n"
    "Compre aqui: https://loja.example.com/produto\n\n"
    "💰Entre no nosso grupo de ofertas:\n"
    "Telegram: https://t.example.com/canal\n"
    "Whatsapp: https://wa.example.com/canal\n"
)

COUPON_LINK_ON_OWN_LINE = (
    "🔥 Placa de Vídeo MSI RTX 5060 8GB\n\n"
    "💵 R$ 2124\n\n"
    "🏷️ Resgate todos os cupons desta página:\n"
    "https://cupom.example.com/b\n\n"
    "✨ Link do produto:\n"
    "https://loja.example.com/produto\n\n"
    "(anuncio)"
)

COUPON_OFF_AQUI = (
    "Placa de vídeo MSI RTX5060 8GB VENTUS 2X OC por R$2.299,00\n\n"
    "Com cupom R$100 OFF aqui: https://cupom.example.com/c\n\n"
    "⚠️Compre aqui: https://loja.example.com/produto\n\n"
    "💰Entre no nosso grupo de ofertas:\n"
    "Telegram: https://t.example.com/canal\n"
)

ARROWS = (
    "🔥 RTX 5060 MSI 8GB SHADOW 2X OC\n\n"
    "💰 R$ 2.142\n"
    "📝 Resgatem o cupom de R$ 100 OFF\n"
    "https://cupom.example.com/d\n\n"
    "⬇️\n"
    "https://loja.example.com/produto\n"
    "https://loja.example.com/produto\n"
)

# Code coupon on the line right above a bare product link: the link is NOT a
# coupon link just because the previous line says "cupom".
CODE_THEN_BARE_LINK = (
    "Placa de Vídeo INNO3D GeForce RTX 5060 Twin X2 8GB - R$2184\n\n"
    "-Cupom QUEROOFERTA\n\n"
    "https://loja.example.com/produto\n\n"
    "(ANÚNCIO)"
)


@pytest.mark.parametrize(
    "text",
    [COUPON_LINK_FIRST, COUPON_LINK_ON_OWN_LINE, COUPON_OFF_AQUI, ARROWS, CODE_THEN_BARE_LINK],
)
def test_purchase_url_is_the_product_not_the_coupon_page(text: str) -> None:
    assert extract_purchase_url(text) == "https://loja.example.com/produto"


def test_purchase_url_skips_channel_footer() -> None:
    text = (
        "RTX 5060 R$ 2.100\n"
        "Telegram: https://t.example.com/canal\n"
        "https://loja.example.com/produto\n"
    )
    assert extract_purchase_url(text) == "https://loja.example.com/produto"


def test_back_in_stock_repost_links_to_the_original_post() -> None:
    text = "Voltou estoque RTX 5060 R$ 2.256\n\nhttps://telegram.me/exemplo/1\n"
    assert extract_purchase_url(text) == "https://telegram.me/exemplo/1"


def test_purchase_url_falls_back_to_coupon_link_when_it_is_the_only_one() -> None:
    text = "RTX 5060 R$ 2.100\nResgate o cupom: https://cupom.example.com/a\n"
    assert extract_purchase_url(text) == "https://cupom.example.com/a"


def test_no_link_no_url() -> None:
    assert extract_purchase_url("RTX 5060 R$ 2.100") is None


def test_link_only_coupon_keeps_discount_and_redeem_link() -> None:
    coupon = extract_coupon(COUPON_LINK_FIRST)
    assert coupon is not None
    assert coupon.code is None  # never "DE" nor "HTTPS"
    assert coupon.discount_abs == Decimal("100")
    assert coupon.url == "https://cupom.example.com/a"


def test_percent_discount() -> None:
    coupon = extract_coupon("RTX 5060 R$ 2.100\ncupom de 10% OFF no app")
    assert coupon is not None
    assert coupon.discount_pct == Decimal("10")


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("🪙 Cupom: QUEROOFERTA", "QUEROOFERTA"),
        ("💵 R$ 2174 com cupom:\nQUEROOFERTA", "QUEROOFERTA"),
        ("-Cupom QUEROOFERTA", "QUEROOFERTA"),
        ("📝 Cupom: NOVA2 ou GRANDE1 ou NOVA3", "NOVA2"),
        ("Use o código Nova10 no carrinho", "NOVA10"),
        ("cupom de desconto: PROMO10", "PROMO10"),
        ("🪙 Cupom para MELI+: OFFMELIMAIS + MELIMAIS7DO8", "OFFMELIMAIS"),
        ("📝 Cupom no APP: 300PAYDAY", "300PAYDAY"),
    ],
)
def test_coupon_code(text: str, code: str) -> None:
    coupon = extract_coupon(text)
    assert coupon is not None
    assert coupon.code == code


@pytest.mark.parametrize(
    "text",
    [
        "🎟️Com cupom de R$100 OFF da Shopee",
        "Resgate o cupom: https://cupom.example.com/a",
        "cupom exclusivo no app",
        "código do produto 912-V537-037",
    ],
)
def test_words_that_are_not_codes(text: str) -> None:
    coupon = extract_coupon(text)
    assert coupon is None or coupon.code is None


def test_discount_without_currency_sign() -> None:
    coupon = extract_coupon("✅ Resgate o cupom de   90    OFF")
    assert coupon is not None
    assert coupon.discount_abs == Decimal("90")


def test_empty_coupon_label_does_not_borrow_the_next_line() -> None:
    coupon = extract_coupon("🏷 Cupom: \n✅ Link: https://loja.example.com/produto")
    assert coupon is None or coupon.code is None


def test_coupon_on_the_product_page() -> None:
    text = (
        "RTX 5060 R$ 2.100\n🎟️ Resgate o cupom no anúncio\nLINK: https://loja.example.com/produto\n"
    )
    coupon = extract_coupon(text)
    assert coupon is not None
    assert coupon.url == extract_purchase_url(text) == "https://loja.example.com/produto"


def test_no_coupon_at_all() -> None:
    assert extract_coupon("RTX 5060 R$ 2.100 https://loja.example.com/produto") is None

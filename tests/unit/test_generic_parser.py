"""Generic parser + triage."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from garimpo.catalog import ModelIndex, load_gpu_catalog
from garimpo.models.raw import RawMessage
from garimpo.parse.generic import GenericParser
from garimpo.parse.triage import passes_triage


def _msg(text: str) -> RawMessage:
    return RawMessage(
        source_id=1,
        tg_msg_id=1,
        text=text,
        has_media=False,
        received_at=datetime.now(UTC),
    )


def test_triage_drops_unrelated() -> None:
    assert not passes_triage("cupom de pizza 50% off")
    assert passes_triage("RTX 5070 Ti em promoção")


def test_generic_parser_happy_path() -> None:
    index = ModelIndex(load_gpu_catalog())
    parser = GenericParser(index)
    offer = parser.parse(
        _msg("🚨 RTX 5070 Ti ASUS Dual — R$ 5.799 no PIX na Kabum")
    )
    assert offer is not None
    assert offer.model_key == "rtx_5070_ti"
    assert offer.price.amount == Decimal("5799")
    assert offer.store == "kabum"
    assert offer.brand == "ASUS"
    assert offer.confidence >= 0.8


def test_installment_not_taken_as_cash() -> None:
    index = ModelIndex(load_gpu_catalog())
    parser = GenericParser(index)
    offer = parser.parse(
        _msg("RTX 5070 Ti 12x R$ 483,25 ou por R$ 5.799 no PIX Terabyte")
    )
    assert offer is not None
    assert offer.price.amount == Decimal("5799")


def test_absurd_price_is_rejected() -> None:
    """A price outside the catalog band is a mis-parse, not a bargain.

    This used to yield an offer with confidence 0.5, which suppressed the alert
    but still wrote the price into price_history — poisoning the baseline the
    offer was being judged against. The band is now a gate.
    """
    index = ModelIndex(load_gpu_catalog())
    parser = GenericParser(index)
    # Well below 0.3 * MSRP and outside price_range [3000, 12000]
    assert parser.parse(_msg("RTX 5070 Ti Kabum R$ 400 no PIX")) is None


# --- Regressão: rodapé comparando SKUs (2026-08) -----------------------------
# Mensagem real de alerta citava "28% a menos que a 9070 XT" e "a 9070 da
# terabyte acima" depois do link. O resolve lia o rodapé, o negative da 9070
# bare rejeitava o produto certo (porque o texto mencionava XT), e o alias
# "9070 xt" casava no comentário — alerta falso de XT a preço de GRE.


_GRE_WITH_XT_FOOTER = """\
🆘 #Pichau - Placa de Video PowerColor Radeon RX 9070 GRE Reaper, 12GB
GDDR6, 192-bit, RX9070GRE-12G-A
Produto

🤑 Valor: R$ 3.699,99
➡️ Link https://www.pichau.com.br/placa-de-video-powercolor-radeon-rx-9070-gre-reaper

Cerca de 15% a menos que a 9070 normal. 28 % A menos que a 9070 XT.
Uma boa opção no caos assim como essa 9070 da terabyte acima
"""


def test_footer_sku_comparison_does_not_steal_model() -> None:
    index = ModelIndex(load_gpu_catalog())
    parser = GenericParser(index)
    # GRE is not in the catalog; the correct outcome is no offer — not XT.
    assert parser.parse(_msg(_GRE_WITH_XT_FOOTER)) is None


def test_real_xt_still_parses_with_store_in_body() -> None:
    index = ModelIndex(load_gpu_catalog())
    parser = GenericParser(index)
    offer = parser.parse(
        _msg(
            "Placa de Vídeo ASUS TUF Radeon RX 9070 XT 16GB — R$ 4.299 no PIX "
            "na Terabyte\nhttps://www.terabyteshop.com.br/produto/9070xt"
        )
    )
    assert offer is not None
    assert offer.model_key == "rx_9070_xt"
    assert offer.store == "terabyte"
    assert offer.price.amount == Decimal("4299")


def test_store_from_product_url_when_body_omits_shop() -> None:
    index = ModelIndex(load_gpu_catalog())
    parser = GenericParser(index)
    offer = parser.parse(
        _msg(
            "ASUS TUF Radeon RX 9070 XT 16GB R$ 4299 PIX\n"
            "https://www.pichau.com.br/placa-rx-9070-xt"
        )
    )
    assert offer is not None
    assert offer.store == "pichau"


def test_alert_payload_includes_coupon_and_purchase_url() -> None:
    index = ModelIndex(load_gpu_catalog())
    parser = GenericParser(index)
    offer = parser.parse(
        _msg(
            "🔥 RTX 5060 TI 8GB Zotac Gaming\n"
            "💰 R$ 2.374 PIX\n"
            "📝 Cupom: MAISECONOMIA\n"
            "⬇️\n"
            "https://example.com/oferta\n"
            "rodapé com 9070 XT e terabyte não deve importar"
        )
    )
    assert offer is not None
    assert offer.model_key == "rtx_5060_ti"
    assert offer.coupon is not None
    assert offer.coupon.code == "MAISECONOMIA"
    assert offer.url == "https://example.com/oferta"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "O sonho, ja é caro eu sei!\n\n"
            "Placa de Vídeo NVIDIA GeForce MSI RTX5070TI 16GB GDDR7 SHADOW 3X\n\n"
            "💵6,991\n\nCupom 90 off aqui\nhttps://cupom.example.com/a\n\n"
            "Link\nhttps://loja.example.com/produto",
            Decimal("6991"),
        ),
        ("RTX 5070 Ti MSI 16GB\n💰 6.945", Decimal("6945")),
        # Emoji before an explicit R$ is left alone.
        ("RTX 5070 Ti MSI 16GB\n💵 R$ 6.945 no PIX", Decimal("6945")),
    ],
)
def test_money_emoji_without_currency_sign(text: str, expected: Decimal) -> None:
    offer = GenericParser(ModelIndex(load_gpu_catalog())).parse(_msg(text))
    assert offer is not None
    assert offer.model_key == "rtx_5070_ti"
    assert offer.price.amount == expected

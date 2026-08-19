"""Generic parser + triage."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

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


def test_absurd_price_lowers_confidence() -> None:
    index = ModelIndex(load_gpu_catalog())
    parser = GenericParser(index)
    # Well below 0.3 * MSRP
    offer = parser.parse(_msg("RTX 5070 Ti Kabum R$ 400 no PIX"))
    assert offer is not None
    assert offer.confidence <= 0.5

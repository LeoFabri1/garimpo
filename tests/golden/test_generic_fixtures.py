"""Golden-style parser checks against anonymized fixtures."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from garimpo.catalog import ModelIndex, load_gpu_catalog
from garimpo.models.raw import RawMessage
from garimpo.parse.generic import GenericParser

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "messages" / "generic"


@pytest.fixture(scope="module")
def parser() -> GenericParser:
    return GenericParser(ModelIndex(load_gpu_catalog()))


@pytest.mark.parametrize(
    ("filename", "model_key", "price"),
    [
        ("001.txt", "rtx_5070_ti", Decimal("5799")),
        ("002.txt", "rx_9070_xt", Decimal("5499")),
        ("003.txt", "rtx_5070_ti", Decimal("5799")),
    ],
)
def test_generic_fixtures(
    parser: GenericParser,
    filename: str,
    model_key: str,
    price: Decimal,
) -> None:
    text = (FIXTURES / filename).read_text(encoding="utf-8")
    msg = RawMessage(
        source_id=1,
        tg_msg_id=1,
        text=text,
        has_media=False,
        received_at=datetime.now(UTC),
    )
    offer = parser.parse(msg)
    assert offer is not None
    assert offer.model_key == model_key
    assert offer.price.amount == price
    assert offer.confidence >= 0.8

"""RAM category: one specific kit, not its RGB / slower / kit siblings."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from garimpo.catalog import ModelIndex, load_catalog_for_watch
from garimpo.models.raw import RawMessage
from garimpo.parse.generic import GenericParser
from garimpo.parse.triage import passes_triage

KEY = "kingston_fury_beast_ddr5_16gb_5600"


def _parse(text: str):  # type: ignore[no-untyped-def]
    parser = GenericParser(ModelIndex(load_catalog_for_watch(["gpu", "ram"])))
    return parser.parse(
        RawMessage(
            source_id=1, tg_msg_id=1, text=text, has_media=False, received_at=datetime.now(UTC)
        )
    )


@pytest.mark.parametrize(
    "title",
    [
        "Memória RAM Kingston Fury Beast, 16GB, 5600MT/s, DDR5, CL36, DIMM, Preto, EXPO"
        " - KF556C36BBE-16",
        "Memória Kingston Fury Beast 16GB DDR5 5600MHz CL36 Preto",
        "Memória DDR5 Kingston Fury Beast, 16GB, 5600MHz, Black, KF556C36BB-16",
        "Kingston Fury Beast DDR5 16GB 5600MHz",
    ],
)
def test_the_kit_is_recognised(title: str) -> None:
    text = f"🔥 {title}\n\n💰 R$ 1.399 no PIX\n\nhttps://loja.example.com/produto"
    assert passes_triage(text)
    offer = _parse(text)
    assert offer is not None
    assert offer.model_key == KEY
    assert offer.price.amount == Decimal("1399")


@pytest.mark.parametrize(
    "title",
    [
        # Seen in the watched channels.
        "Memória Kingston Fury Beast, 16GB, 4800MHz, DDR5, CL38, Preto - KF548C38BB-16",
        "Memória DDR5 Kingston Fury Beast EXPO, RGB, 8GB, 6000Mhz, Black",
        "Memória Ram Crucial Basics 16gb Ddr5 5600mhz Udimm Preto AM5",
        # Siblings of the same line.
        "Memória Kingston Fury Beast RGB, 16GB, 5600MT/s, DDR5, CL36 - KF556C36BBEA-16",
        "Memória Kingston Fury Beast, 32GB (2x16GB), 5600MT/s, DDR5, CL36",
        "Memória Kingston Fury Beast, 16GB, 5600MT/s, DDR5, CL40 - KF556C40BB-16",
        "Memória Notebook Kingston Fury Impact 16GB DDR5 5600 SODIMM",
    ],
)
def test_siblings_are_not_the_kit(title: str) -> None:
    offer = _parse(f"🔥 {title}\n\n💰 R$ 1.399\n\nhttps://loja.example.com/produto")
    assert offer is None or offer.model_key != KEY


KEY_32 = "kingston_fury_beast_ddr5_32gb_5600"
KEY_64 = "kingston_fury_beast_ddr5_64gb_2x32_5600"


@pytest.mark.parametrize(
    ("title", "key"),
    [
        (
            "Memória RAM Kingston Fury Beast, 32GB, 5600MT/s, DDR5, CL36, Preto, EXPO"
            " - KF556C36BBE-32",
            KEY_32,
        ),
        ("Memória Kingston Fury Beast 32GB DDR5 5600MHz CL36 Preto", KEY_32),
        ("Memória DDR5 Kingston Fury Beast, 32GB, 5600MHz, Black, KF556C36BB-32", KEY_32),
        (
            "Memória RAM Kingston Fury Beast, 64GB (2x32GB), 5600MT/s, DDR5, CL36, EXPO"
            " - KF556C36BBEK2-64",
            KEY_64,
        ),
        ("Kit Memória Kingston Fury Beast 64GB (2x32GB) DDR5 5600MHz CL36", KEY_64),
        ("Memória Kingston Fury Beast 2x32GB DDR5 5600MHz", KEY_64),
        ("Memória DDR5 Kingston Fury Beast, 64GB, 5600MHz, KF556C36BBK2-64", KEY_64),
    ],
)
def test_bigger_sizes_of_the_same_line(title: str, key: str) -> None:
    offer = _parse(f"🔥 {title}\n\n💰 R$ 2.999\n\nhttps://loja.example.com/produto")
    assert offer is not None
    assert offer.model_key == key


@pytest.mark.parametrize(
    "title",
    [
        "Memória Kingston Fury Beast RGB, 32GB, 5600MT/s, DDR5, CL36 - KF556C36BBEA-32",
        "Memória Kingston Fury Beast, 32GB, 5600MT/s, DDR5, CL40 - KF556C40BB-32",
        "Memória Kingston Fury Beast, 32GB (2x16GB), 5600MT/s, DDR5, CL36 - KF556C36BBEK2-32",
        "Memória Kingston Fury Beast RGB, 64GB (2x32GB), 5600MT/s, DDR5 - KF556C36BBEAK2-64",
        "Memória Kingston Fury Beast, 64GB (2x32GB), 6000MT/s, DDR5, CL30 - KF560C30BBEK2-64",
        "Memória Kingston Fury Beast, 128GB (4x32GB), 5600MT/s, DDR5",
        "CORSAIR VENGEANCE RGB DDR5 32GB (2x16GB) 6000MHz CL36",
    ],
)
def test_bigger_siblings_are_rejected(title: str) -> None:
    offer = _parse(f"🔥 {title}\n\n💰 R$ 2.999\n\nhttps://loja.example.com/produto")
    assert offer is None or offer.model_key not in {KEY, KEY_32, KEY_64}

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
    assert passes_triage(text, {"ram"})
    assert not passes_triage(text)
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


KEY_64 = "ddr5_64gb_2x32_kit"


@pytest.mark.parametrize(
    ("title", "key"),
    [
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
        "Memória Kingston Fury Beast, 128GB (4x32GB), 5600MT/s, DDR5",
        "CORSAIR VENGEANCE RGB DDR5 32GB (2x16GB) 6000MHz CL36",
    ],
)
def test_bigger_siblings_are_rejected(title: str) -> None:
    offer = _parse(f"🔥 {title}\n\n💰 R$ 2.999\n\nhttps://loja.example.com/produto")
    assert offer is None or offer.model_key not in {KEY, KEY_64}


@pytest.mark.parametrize(
    "title",
    [
        "Kit Memória Corsair Vengeance 64GB (2x32GB) DDR5 6000MHz CL30",
        "Memória Kingston Fury Beast RGB, 64GB (2x32GB), 5600MT/s, DDR5 - KF556C36BBEAK2-64",
        "Memória Kingston Fury Beast, 64GB (2x32GB), 6000MT/s, DDR5, CL30 - KF560C30BBEK2-64",
        "G.Skill Trident Z5 RGB 64GB (2x32GB) DDR5-6000 CL30",
        "Memória XPG Lancer Blade 2x32GB DDR5 6000MHz",
        "Kit Memória RAM TeamGroup T-Create 64GB 2 x 32GB DDR5 6400MHz",
        "Kit Memoria Ram Crucial Pro 64gb (2x32gb) Ddr5 5600mhz",
    ],
)
def test_any_ddr5_2x32_desktop_kit(title: str) -> None:
    text = f"🔥 {title}\n\n💰 R$ 3.099\n\nhttps://loja.example.com/produto"
    assert passes_triage(text, {"ram"})
    offer = _parse(text)
    assert offer is not None
    assert offer.model_key == KEY_64
    assert offer.price.amount == Decimal("3099")


@pytest.mark.parametrize(
    "title",
    [
        "Kit Memória Corsair Vengeance LPX 64GB (2x32GB) DDR4 3200MHz",
        "Kit Memória Notebook Kingston Fury Impact 64GB (2x32GB) DDR5 5600 SODIMM",
        "Memória Crucial 64GB (2x32GB) DDR5 5600 SO-DIMM para laptop",
        "Kit Memória Corsair Vengeance 128GB (4x32GB) DDR5 5600",
        "Kit Memória Corsair Vengeance 32GB (2x16GB) DDR5 6000",
        "Memória Kingston Server Premier 64GB (2x32GB) DDR5 4800 RDIMM ECC Registrada",
        "Kit Memória Corsair 96GB (2x48GB) DDR5 6000",
        # A whole machine is not a memory kit.
        "PC Gamer Pichau, AMD Ryzen 9 9950X, GeForce RTX 5070 Ti, 64GB (2x32GB) DDR5, SSD 2TB",
        "Computador Workstation Intel Core i9, 64GB (2x32GB) DDR5",
    ],
)
def test_not_a_desktop_ddr5_2x32_kit(title: str) -> None:
    offer = _parse(f"🔥 {title}\n\n💰 R$ 3.099\n\nhttps://loja.example.com/produto")
    assert offer is None or offer.model_key != KEY_64


KEY_2X16 = "ddr5_32gb_2x16_kit"


@pytest.mark.parametrize(
    "title",
    [
        "Memória RAM Kingston Fury Beast, 32GB, 5600MT/s, DDR5, CL36, EXPO - KF556C36BBE-32",
        "Memória Kingston Fury Beast 32GB DDR5 5600MHz CL36 Preto",
        "Memória DDR5 Rise Mode Zeus, 32GB, 6000MHz",
    ],
)
def test_a_single_32gb_stick_is_no_longer_tracked(title: str) -> None:
    """O pente avulso de 32GB saiu do catálogo, e não deve cair em outro produto.

    Um pente de 32 não serve ao par que o de 16 existe para completar, e no
    arquivo inteiro uma única mensagem cita 32GB de DDR5 — não paga a manutenção.
    """
    offer = _parse(f"🔥 {title}\n\n💰 R$ 2.999\n\nhttps://loja.example.com/produto")
    assert offer is None


@pytest.mark.parametrize(
    "title",
    [
        "Kit Memória Corsair Vengeance 32GB (2x16GB) DDR5 6000MHz CL30",
        "Memória Kingston Fury Beast, 32GB (2x16GB), 5600MT/s, DDR5, CL36",
        "G.Skill Trident Z5 RGB 32GB (2x16GB) DDR5-6000 CL30",
        "Memória XPG Lancer 2x16GB DDR5 6000MHz",
        "Kit Memória RAM TeamGroup T-Create 32GB 2 x 16GB DDR5 6400MHz",
        "Kit Memoria Ram Crucial Pro 32gb (2x16gb) Ddr5 5600mhz",
    ],
)
def test_any_ddr5_2x16_desktop_kit(title: str) -> None:
    text = f"🔥 {title}\n\n💰 R$ 899\n\nhttps://loja.example.com/produto"
    assert passes_triage(text, {"ram"})
    offer = _parse(text)
    assert offer is not None
    assert offer.model_key == KEY_2X16
    assert offer.price.amount == Decimal("899")


def test_the_5060_ti_is_not_a_memory_kit() -> None:
    """"2X 16GB" é nome de placa de vídeo nesses canais, não configuração de kit.

    Texto real, 23 ocorrências no arquivo. Sem exigir "ddr5" no produto, o
    alias "2x16gb" transformaria esta placa em memória — e a R$ 3.671 ela
    entraria no baseline do kit como se fosse um kit caríssimo.
    """
    text = (
        "🔥 Placa de Vídeo NVIDIA GeForce MSI RTX5060TI Ventus OC Black Plus "
        "2X 16GB - 128 Bits - HDMI/3x DP\n\n💰 R$ 3.671\n\n"
        "https://loja.example.com/produto"
    )
    offer = _parse(text)
    assert offer is not None
    assert offer.model_key == "rtx_5060_ti"


@pytest.mark.parametrize(
    "title",
    [
        "Kit Memória Corsair Vengeance LPX 32GB (2x16GB) DDR4 3200MHz",
        "Memória Ram Ddr4 Spectrum Blitz S 2 x 16gb 3200MHz",
        "Kit Memória Notebook Kingston Fury Impact 32GB (2x16GB) DDR5 5600 SODIMM",
        "Memória Crucial 32GB (2x16GB) DDR5 5600 SO-DIMM para laptop",
        "Kit Memória Corsair Vengeance 64GB (4x16GB) DDR5 5600",
        "Kit Memória Corsair Vengeance 64GB (2x32GB) DDR5 6000",
        "Memória Kingston Server Premier 32GB (2x16GB) DDR5 4800 RDIMM ECC Registrada",
        # Uma máquina inteira não é kit de memória.
        "PC Gamer Pichau, AMD Ryzen 7 9800X3D, GeForce RTX 5070, 32GB (2x16GB) DDR5",
        "Computador Workstation Intel Core i9, 32GB (2x16GB) DDR5",
    ],
)
def test_not_a_desktop_ddr5_2x16_kit(title: str) -> None:
    offer = _parse(f"🔥 {title}\n\n💰 R$ 899\n\nhttps://loja.example.com/produto")
    assert offer is None or offer.model_key != KEY_2X16

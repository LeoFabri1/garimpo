"""Catalog / resolver tests."""

from __future__ import annotations

import pytest

from garimpo.catalog import ModelIndex, load_catalog_for_watch, load_gpu_catalog


def test_load_gpu_catalog() -> None:
    catalog = load_gpu_catalog()
    assert "rtx_5070_ti" in catalog.products
    assert catalog.products["rtx_5070_ti"].perf == 100
    assert "rtx_4090" in catalog.products
    assert "rx_7800_xt" in catalog.products


def test_longest_alias_wins_5070_ti() -> None:
    index = ModelIndex(load_gpu_catalog())
    result = index.resolve("Promoção GeForce RTX 5070 Ti ASUS Dual")
    assert result is not None
    assert result.model_key == "rtx_5070_ti"


def test_bare_5070_is_not_ti() -> None:
    index = ModelIndex(load_gpu_catalog())
    result = index.resolve("RTX 5070 12GB Kabum R$ 4999")
    assert result is not None
    assert result.model_key == "rtx_5070"


def test_9070_xt_not_bare_9070() -> None:
    index = ModelIndex(load_gpu_catalog())
    result = index.resolve("RX 9070 XT XFX R$ 5499")
    assert result is not None
    assert result.model_key == "rx_9070_xt"


def test_4070_super_not_plain_4070() -> None:
    index = ModelIndex(load_gpu_catalog())
    result = index.resolve("RTX 4070 Super MSI R$ 3899")
    assert result is not None
    assert result.model_key == "rtx_4070_super"


def test_notebook_beats_desktop_4060_when_merged() -> None:
    index = ModelIndex(load_catalog_for_watch(["gpu", "notebook"]))
    result = index.resolve("Notebook RTX 4060 Acer Nitro R$ 5499")
    assert result is not None
    assert result.model_key == "notebook_rtx_4060"


def test_desktop_4060_rejects_notebook_word() -> None:
    index = ModelIndex(load_gpu_catalog())
    result = index.resolve("RTX 4060 ASUS Dual OC desktop R$ 1899")
    assert result is not None
    assert result.model_key == "rtx_4060"


def test_desktop_4060_not_chosen_for_notebook_text() -> None:
    index = ModelIndex(load_gpu_catalog())
    # GPU-only catalog: notebook aliases absent → should not map to desktop
    # when "notebook" triggers negative on desktop 4060
    result = index.resolve("notebook rtx 4060 barato")
    assert result is None or result.model_key != "rtx_4060"


def test_7900_xtx_not_xt() -> None:
    index = ModelIndex(load_gpu_catalog())
    result = index.resolve("RX 7900 XTX Sapphire R$ 6200")
    assert result is not None
    assert result.model_key == "rx_7900_xtx"


def test_cpu_9800_not_7800() -> None:
    index = ModelIndex(load_catalog_for_watch(["cpu"]))
    result = index.resolve("AMD Ryzen 7 9800X3D R$ 2999")
    assert result is not None
    assert result.model_key == "ryzen_7_9800x3d"


# --- Regressions from real @iskandarsouza / @ofertasadrenaline traffic (2026-08)
# Fuzzy matching turned "product missing from catalog" into "wrong product in
# catalog": RX 9060 XT resolved as rx_9070_xt at confidence 0.9375, above
# MIN_CONFIDENCE, and fired 16 of 126 alerts for a card that was not the card.
# And a prebuilt machine counted as the bare component it contains.

@pytest.mark.parametrize(
    "text",
    [
        "PC Gamer Mancer, AMD Ryzen 5 5500, GeForce RTX 2060 6GB, 16GB DDR4",
        "GeForce RTX 2060 Super",
        "Placa de Video ASUS Radeon RX 9060 XT Dual White, 16GB, GDDR6",
        "Placa de Vídeo ASRock RX 9060 XT CL de 16GB",
    ],
)
def test_fuzzy_may_not_invent_a_model_number(text: str) -> None:
    """One digit separates two products; a card absent from the catalog must
    stay unmatched rather than snap onto its nearest neighbour."""
    assert ModelIndex(load_gpu_catalog()).resolve(text.lower()) is None


@pytest.mark.parametrize(
    "text",
    [
        "PC Gamer Pichau Ísis VI, AMD Ryzen 5 5500, GeForce RTX 5060 8GB, 16GB DDR4",
        "Computador Pichau Gamer Ninigi, AMD Ryzen 7 5700X, GeForce RTX 5070",
        "Notebook Gamer Predator Helios 16, Intel Core Ultra 7 255HX, RTX5070",
    ],
)
def test_prebuilt_machine_is_not_the_component(text: str) -> None:
    """A PC Gamer at R$ 4.800 is not an RTX 5060 at R$ 4.800."""
    assert ModelIndex(load_gpu_catalog()).resolve(text.lower()) is None


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Placa de Video MSI GeForce RTX 5060 Shadow 2X OC 8GB GDDR7", "rtx_5060"),
        ("Placa de Vídeo ASUS TUF Radeon RX 9070 XT 16GB GDDR6", "rx_9070_xt"),
        ("Placa De Video Palit Geforce RTX 5060 8GB Infinity 2 Oc", "rtx_5060"),
        ("MSI RTX 5070 TI 16GB GDDR7 Shadow 3x OC", "rtx_5070_ti"),
    ],
)
def test_real_cards_still_resolve(text: str, expected: str) -> None:
    """The guards must not cost us the offers that matter."""
    result = ModelIndex(load_gpu_catalog()).resolve(text.lower())
    assert result is not None
    assert result.model_key == expected

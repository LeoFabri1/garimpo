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


@pytest.mark.parametrize(
    "text",
    [
        "Placa de Video PowerColor Radeon RX 9070 GRE Reaper, 12GB, GDDR6",
        "PowerColor RX9070GRE-12G-A Reaper 12GB",
        "Radeon RX 9070 GRE 12GB GDDR6",
    ],
)
def test_9070_gre_is_not_9070_or_xt(text: str) -> None:
    """GRE is a different SKU (12GB); snapping it onto 9070/XT poisons both."""
    assert ModelIndex(load_gpu_catalog()).resolve(text.lower()) is None


# --- Nomes colados: "5070Ti", "RTX4060", "ryzen5 5600" -----------------------
#
# Aparecem pouco nos canais, mas quando aparecem a oferta é perdida inteira.
# Os produtos abaixo não têm alias colado escrito à mão — quem resolve é o
# alias que trata o próprio espaço como opcional.
#
# Os textos mantêm "notebook" vizinho do modelo de propósito: casar o token
# de classe a distância ("Notebook Gamer Lenovo LOQ ... RTX 4060") não
# funciona hoje nem com espaços, e é outro problema.


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Notebook RTX4050 Acer Nitro V i5 16GB", "notebook_rtx_4050"),
        ("Notebook RTX4060 Lenovo LOQ i7 512GB", "notebook_rtx_4060"),
        ("Lenovo LOQ RTX4070 Notebook Ryzen 7", "notebook_rtx_4070"),
        ("Laptop RTX4080 MSI Raider i9", "notebook_rtx_4080"),
        ("Notebook RTX3050 Acer Nitro 5 i5", "notebook_rtx_3050"),
    ],
)
def test_glued_notebook_gpu_resolves(text: str, expected: str) -> None:
    index = ModelIndex(load_catalog_for_watch(["gpu", "notebook"]))
    result = index.resolve(text.lower())
    assert result is not None
    assert result.model_key == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Placa de Video Sapphire Pulse RX7600 8GB GDDR6", "rx_7600"),
        ("Placa de Video Intel ARCB580 Limited Edition 12GB", "arc_b580"),
    ],
)
def test_glued_desktop_gpu_resolves(text: str, expected: str) -> None:
    result = ModelIndex(load_gpu_catalog()).resolve(text.lower())
    assert result is not None
    assert result.model_key == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Processador AMD Ryzen5 5600 AM4 sem video", "ryzen_5_5600"),
        ("Processador AMD Ryzen5 7600 AM5", "ryzen_5_7600"),
    ],
)
def test_glued_cpu_resolves(text: str, expected: str) -> None:
    index = ModelIndex(load_catalog_for_watch(["gpu", "cpu"]))
    result = index.resolve(text.lower())
    assert result is not None
    assert result.model_key == expected


def test_glued_pass_still_honours_the_ti_suffix() -> None:
    """Colar não pode deixar o irmão mais curto vencer o mais específico."""
    result = ModelIndex(load_gpu_catalog()).resolve("sapphire rx7600xt 16gb")
    assert result is not None
    assert result.model_key == "rx_7600_xt"


def test_exact_pass_declines_a_letter_suffix_false_positive() -> None:
    """"rtx 5070 titan" contém "rtx 5070 ti" — o limite tira o passe exato fora.

    O fuzzy ainda entrega rtx_5070_ti aqui, porque `partial_ratio` dá 100 para
    um alias que é substring do texto. Consertar isso é mexer no corte do
    fuzzy, não no casamento de alias, e fica para outra mudança.
    """
    result = ModelIndex(load_gpu_catalog()).resolve("placa de video rtx 5070 titan oc")
    assert result is not None
    assert result.method == "fuzzy"


def test_boundary_still_allows_a_digit_after_the_alias() -> None:
    """Texto totalmente colado: o "16gb" logo depois do "ti" é legítimo."""
    result = ModelIndex(load_gpu_catalog()).resolve("msi rtx5070ti16gb shadow")
    assert result is not None
    assert result.model_key == "rtx_5070_ti"


def test_glued_notebook_does_not_leak_into_the_desktop_card() -> None:
    index = ModelIndex(load_catalog_for_watch(["gpu", "notebook"]))
    result = index.resolve("notebook rtx4060 i7")
    assert result is not None
    assert result.model_key == "notebook_rtx_4060"


def test_glued_notebook_does_not_leak_into_a_sibling_sku() -> None:
    index = ModelIndex(load_catalog_for_watch(["gpu", "notebook"]))
    result = index.resolve("notebook rtx4050 i5 8gb")
    assert result is not None
    assert result.model_key == "notebook_rtx_4050"


def test_spaced_names_keep_the_plain_exact_method() -> None:
    """O passe colado é aditivo: não deve capturar o que já funcionava."""
    result = ModelIndex(load_gpu_catalog()).resolve("geforce rtx 5070 ti asus dual")
    assert result is not None
    assert result.model_key == "rtx_5070_ti"
    assert result.method == "exact"


# --- required_aliases: o token de classe longe do modelo --------------------
#
# Anúncio de notebook quase nunca encosta "Notebook" no nome da GPU — o modelo
# aparece sozinho, quinze palavras depois. Exigir os dois juntos num alias só
# custou 231 das 251 mensagens de notebook do arquivo. Agora o alias carrega só
# o modelo e `required_aliases` cobra o token de classe em qualquer posição.

NOTEBOOK_REAL = [
    (
        "Notebook Gamer Acer Nitro V15 ANV15-52-56PD Intel Core i5-13420H de 13ªG "
        "8GB RAM 512GB SSD RTX4050 Windows 11 15.6”",
        "notebook_rtx_4050",
    ),
    (
        "Notebook Gamer Acer Predator Helios Neo PHN16-72-75TX Intel Core "
        "i7-14700HX de 14ªG 32GB RAM 512GB SSD RTX4070 W11 Home 16",
        "notebook_rtx_4070",
    ),
    (
        "Notebook Gamer Lenovo LOQ 15IRX9 i7-13650HX 16GB 512GB SSD RTX 4060 "
        "Windows 11",
        "notebook_rtx_4060",
    ),
    (
        "Laptop ASUS TUF Gaming A15 Ryzen 7 7435HS 16GB 512GB RTX 3050 6GB",
        "notebook_rtx_3050",
    ),
]


@pytest.mark.parametrize(("text", "expected"), NOTEBOOK_REAL)
def test_class_token_far_from_the_model(text: str, expected: str) -> None:
    index = ModelIndex(load_catalog_for_watch(["gpu", "notebook"]))
    result = index.resolve(text.lower())
    assert result is not None
    assert result.model_key == expected


def test_desktop_card_keeps_the_shared_alias() -> None:
    """"rtx 4060" agora pertence a dois produtos; sem "notebook" é a avulsa."""
    index = ModelIndex(load_catalog_for_watch(["gpu", "notebook"]))
    result = index.resolve("placa de video asus dual rtx 4060 oc 8gb gddr6")
    assert result is not None
    assert result.model_key == "rtx_4060"


def test_notebook_product_needs_its_class_token() -> None:
    """Sem "notebook" no texto o produto de notebook não pode responder.

    Não existe RTX 4050 avulsa no catálogo, então o resultado certo é nada —
    e não `notebook_rtx_4050`.
    """
    index = ModelIndex(load_catalog_for_watch(["gpu", "notebook"]))
    assert index.resolve("placa de video rtx 4050 8gb") is None


def test_notebook_still_rejects_a_sibling_sku_in_the_same_text() -> None:
    index = ModelIndex(load_catalog_for_watch(["gpu", "notebook"]))
    text = "notebook gamer rtx 4050 melhor que a rtx 4060 da geracao passada"
    assert index.resolve(text.lower()) is None

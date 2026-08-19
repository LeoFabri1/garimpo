"""Catalog / resolver tests."""

from __future__ import annotations

from garimpo.catalog import ModelIndex, load_gpu_catalog


def test_load_gpu_catalog() -> None:
    catalog = load_gpu_catalog()
    assert "rtx_5070_ti" in catalog.products
    assert catalog.products["rtx_5070_ti"].perf == 100


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

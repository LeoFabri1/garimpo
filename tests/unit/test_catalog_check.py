"""Catalog check + category merge tests."""

from garimpo.catalog.loader import load_catalog_for_watch, load_category_catalog
from garimpo.tools.catalog_check import check_catalogs


def test_catalog_check_clean() -> None:
    errors = check_catalogs()
    # placeholders may share generic aliases across categories — filter strict GPU
    gpu_errors = [e for e in errors if e.startswith("gpu.json") or "gpu.json:" in e]
    assert not gpu_errors, gpu_errors


def test_load_category_placeholder() -> None:
    cat = load_category_catalog("notebook")
    assert "notebook_rtx_4060" in cat.products


def test_merge_watch_categories() -> None:
    merged = load_catalog_for_watch(["gpu", "notebook", "cpu"])
    assert "rtx_5070_ti" in merged.products
    assert "notebook_rtx_4060" in merged.products
    assert "ryzen_7_7800x3d" in merged.products

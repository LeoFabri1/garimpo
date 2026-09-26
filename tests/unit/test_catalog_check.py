"""Catalog check + category merge tests."""

import json
from pathlib import Path

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


# --- alias compartilhado entre produtos que não podem casar juntos ----------

_META = {
    "perf_basis": "t",
    "perf_reference": "t",
    "updated_at": "2026-01-01",
}


def _write(root: Path, gpu: dict, category: dict) -> None:
    (root / "gpu.json").write_text(json.dumps({"meta": _META, "products": gpu}))
    (root / "categories").mkdir(exist_ok=True)
    (root / "categories" / "notebook.json").write_text(
        json.dumps({"meta": _META, "products": category})
    )


def _product(aliases: list[str], **extra: object) -> dict:
    return {"display": "d", "vendor": "v", "perf": 1, "aliases": aliases, **extra}


def test_shared_alias_is_allowed_when_requirements_are_disjoint(tmp_path: Path) -> None:
    """"rtx 4060" tem dois donos, mas só um pode casar em cada texto.

    O desktop rejeita "notebook" por negative_alias; o de notebook exige o
    token. Nunca respondem ao mesmo texto, então não há ambiguidade a acusar.
    """
    _write(
        tmp_path,
        {"rtx_4060": _product(["rtx 4060"], negative_aliases=["notebook", "laptop"])},
        {"notebook_rtx_4060": _product(["rtx 4060"], required_aliases=["notebook"])},
    )
    assert check_catalogs(tmp_path) == []


def test_shared_alias_is_still_an_error_without_a_requirement(tmp_path: Path) -> None:
    """Sem `required_aliases` a duplicata volta a ser ambiguidade real."""
    _write(
        tmp_path,
        {"rtx_4060": _product(["rtx 4060"])},
        {"notebook_rtx_4060": _product(["rtx 4060"])},
    )
    errors = check_catalogs(tmp_path)
    assert any("rtx 4060" in e and "duplicado" in e for e in errors), errors


def test_required_alias_may_not_also_be_negative(tmp_path: Path) -> None:
    """Exigir e proibir o mesmo token torna o produto incasável."""
    _write(
        tmp_path,
        {"rtx_4060": _product(["rtx 4060"])},
        {
            "notebook_rtx_4060": _product(
                ["rtx 4060 notebook"],
                required_aliases=["notebook"],
                negative_aliases=["notebook"],
            )
        },
    )
    errors = check_catalogs(tmp_path)
    assert any("notebook" in e and "required" in e for e in errors), errors

"""A pip-installed garimpo must find its own catalog.

The wheel ships the catalog via hatch force-include; the loader has to look in
exactly the directory hatch writes it to. These two live in different files, so
this test couples them: change one without the other and it fails here instead
of in a stranger's terminal.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

import garimpo
from garimpo.catalog import loader
from garimpo.catalog.loader import CatalogNotFoundError, catalog_dir_candidates

_PYPROJECT = Path(__file__).resolve().parents[2] / "pyproject.toml"


def _force_include() -> dict[str, str]:
    data = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))
    return data["tool"]["hatch"]["build"]["targets"]["wheel"]["force-include"]


def test_loader_looks_where_the_wheel_ships_the_catalog() -> None:
    target = _force_include()["catalog"]  # e.g. "garimpo/data/catalog"
    package_root = Path(garimpo.__file__).resolve().parent

    # force-include targets are relative to site-packages, so strip the leading
    # package name to get the path inside the installed package.
    parts = Path(target).parts
    assert parts[0] == package_root.name, (
        f"force-include target {target!r} does not start with the package name"
    )
    expected = package_root.joinpath(*parts[1:])

    assert expected in [p.resolve() for p in catalog_dir_candidates()], (
        f"loader never looks in {expected} — a pip install would find no catalog"
    )


def test_missing_catalog_lists_every_path_tried(monkeypatch: pytest.MonkeyPatch) -> None:
    bogus = [Path("/nonexistent/one"), Path("/nonexistent/two")]
    monkeypatch.setattr(loader, "catalog_dir_candidates", lambda: bogus)

    with pytest.raises(CatalogNotFoundError) as excinfo:
        loader.default_catalog_dir()

    message = str(excinfo.value)
    for path in bogus:
        assert str(path) in message
    assert "GARIMPO_CATALOG_DIR" in message


def test_env_override_wins(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("GARIMPO_CATALOG_DIR", str(tmp_path))
    assert catalog_dir_candidates()[0] == tmp_path

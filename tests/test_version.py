"""The version must be single-sourced from pyproject, not copied around."""

from __future__ import annotations

import tomllib
from pathlib import Path

import garimpo
from garimpo import DEFAULT_APP_VERSION, __version__

_PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"


def test_version_is_semver_like() -> None:
    parts = __version__.split(".")
    assert len(parts) >= 2
    assert all(p.isdigit() for p in parts[:2])


def test_version_matches_pyproject() -> None:
    declared = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))["project"]["version"]
    assert __version__ == declared, (
        f"installed metadata says {__version__} but pyproject says {declared} — "
        "reinstall, or the release would ship a mismatched version"
    )


def test_no_hardcoded_version_outside_pyproject() -> None:
    """A bumped release must not leave stale copies behind."""
    src = Path(garimpo.__file__).resolve().parent
    offenders = []
    for path in src.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if f'"garimpo {__version__}"' in text or f"'garimpo {__version__}'" in text:
            offenders.append(path.name)
    assert not offenders, f"hardcoded app version in: {offenders}"


def test_app_version_derives_from_package_version() -> None:
    assert DEFAULT_APP_VERSION == f"garimpo {__version__}"

"""Smoke test: package imports and reports a version."""

from garimpo import __version__


def test_version_is_semver_like() -> None:
    parts = __version__.split(".")
    assert len(parts) >= 2
    assert all(p.isdigit() for p in parts[:2])

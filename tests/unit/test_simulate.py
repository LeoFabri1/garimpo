"""Simulate report smoke test."""

from pathlib import Path

from garimpo.settings import load_settings
from garimpo.tools.simulate import simulate


def test_simulate_empty_db(tmp_path: Path) -> None:
    settings = load_settings(Path("config/quickstart.yaml"))
    settings.storage.path = str(tmp_path / "empty.db")
    report = simulate(settings, days=30)
    assert report.offers == 0
    assert report.by_level == {}

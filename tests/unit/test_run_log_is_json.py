"""`garimpo run` writes nothing but log records to stdout.

The daemon's stdout is data/garimpo.log, JSON one record per line. A plain
"garimpo run: listening…" echo on each start broke `daemon logs -f | jq .`.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from structlog.testing import capture_logs
from typer.testing import CliRunner

from garimpo.cli import app


class _Pipeline:
    def __init__(self, *args: object, **kwargs: object) -> None:
        pass

    def close(self) -> None:
        pass


async def _run_daemon(*args: object, **kwargs: object) -> None:
    return None


def test_live_run_start_is_a_log_record(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = tmp_path / "c.yaml"
    cfg.write_text(
        "sources: ['@exemplo']\n"
        "watch:\n  - name: g\n    category: gpu\n    max_price: 5000\n"
        f"storage:\n  path: {tmp_path / 'g.db'}\nlogging:\n  format: json\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("garimpo.logging.configure_logging", lambda **_: None)
    monkeypatch.setattr("garimpo.ingest.factory.build_client", lambda settings: object())
    monkeypatch.setattr("garimpo.pipeline.Pipeline", _Pipeline)
    monkeypatch.setattr("garimpo.ingest.listener.run_daemon", _run_daemon)

    with capture_logs() as logs:
        result = CliRunner().invoke(app, ["run", "-c", str(cfg)])

    assert result.exit_code == 0, result.output
    assert result.output.strip() == ""
    assert any(entry["event"] == "listening" for entry in logs)

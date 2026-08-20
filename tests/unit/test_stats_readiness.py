"""`stats` precisa dizer se o score ligou, não só contar linhas.

Abaixo de scoring.min_samples, score/rules.py cai num atalho que é só filtro de
preço máximo. O usuário recebe alertas e acredita que são estatísticos — e essa
diferença era invisível.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from garimpo.pipeline import stats_snapshot
from garimpo.settings import Settings, load_settings
from garimpo.store.db import connect
from garimpo.store.repo import history as history_repo


def _settings(tmp_path: Path) -> Settings:
    st = load_settings(Path("config/quickstart.yaml"))
    st.storage.path = str(tmp_path / "s.db")
    st.alerts.channel = "console"
    return st


def _seed(st: Settings, model: str, n: int, *, days_ago: int = 1) -> None:
    conn = connect(st.storage.path)
    when = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=days_ago)
    try:
        for i in range(n):
            history_repo.insert_history(
                conn, model_key=model, price=2000.0 + i, observed_at=when,
                origin="telegram", store="kabum",
            )
    finally:
        conn.close()


def test_empty_db_reports_no_baseline(tmp_path: Path) -> None:
    st = _settings(tmp_path)
    b = stats_snapshot(st)["baseline"]
    assert b["with_baseline"] == []
    assert b["without_baseline"], "modelos vigiados deveriam aparecer como sem baseline"
    assert b["warning"] and "NÃO são estatísticos" in b["warning"]


def test_model_crossing_min_samples_is_marked(tmp_path: Path) -> None:
    st = _settings(tmp_path)
    alvo = next(iter(st.watch[0].models))
    from garimpo.catalog import ModelIndex, load_gpu_catalog

    key = ModelIndex(load_gpu_catalog()).resolve(alvo.lower()).model_key
    _seed(st, key, st.scoring.min_samples)
    b = stats_snapshot(st)["baseline"]
    assert key in b["with_baseline"]
    assert key not in b["without_baseline"]
    assert b["watched"][key] == st.scoring.min_samples


def test_samples_outside_the_window_do_not_count(tmp_path: Path) -> None:
    """Janela deslizante: amostra velha não sustenta baseline."""
    st = _settings(tmp_path)
    from garimpo.catalog import ModelIndex, load_gpu_catalog

    key = ModelIndex(load_gpu_catalog()).resolve(next(iter(st.watch[0].models)).lower()).model_key
    _seed(st, key, st.scoring.min_samples, days_ago=st.scoring.window_days + 5)
    b = stats_snapshot(st)["baseline"]
    assert b["watched"][key] == 0
    assert key in b["without_baseline"]


def test_parse_rate_is_none_when_nothing_reached_the_parser(tmp_path: Path) -> None:
    assert stats_snapshot(_settings(tmp_path))["parse_rate"] is None

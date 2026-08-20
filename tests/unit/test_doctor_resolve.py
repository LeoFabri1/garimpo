"""doctor resolve as sources contra o Telegram, sem poder quebrar por isso."""

from __future__ import annotations

import asyncio

import pytest

from garimpo.ingest.base import SourceRef
from garimpo.tools.doctor import _resolve_sources


class _Settings:
    def __init__(self, usernames: list[str]) -> None:
        self.sources = [
            type("S", (), {"username": u, "id": None, "parser": "generic", "enabled": True})()
            for u in usernames
        ]


class _Client:
    """Resolve tudo, menos quem estiver em `falham`."""

    def __init__(self, falham: set[str] | None = None, trava: set[str] | None = None) -> None:
        self.falham = falham or set()
        self.trava = trava or set()
        self.chamadas = 0

    async def resolve_source(self, src: SourceRef) -> SourceRef:
        self.chamadas += 1
        if src.username in self.trava:
            await asyncio.sleep(60)
        if src.username in self.falham:
            raise ValueError("username inválido")
        return SourceRef(tg_id=123, username=src.username, parser=src.parser)


def _run(client: _Client, usernames: list[str]) -> list:
    return asyncio.run(_resolve_sources(client, _Settings(usernames)))


def test_resolved_source_passes() -> None:
    res = _run(_Client(), ["canal_bom"])
    assert len(res) == 1 and res[0].ok and "tg_id=123" in (res[0].detail or "")


def test_unresolvable_source_is_a_failure_not_a_warning() -> None:
    """Antes isto era warning no meio do `run`, com o daemon seguindo sem a fonte."""
    res = _run(_Client(falham={"typo"}), ["typo"])
    assert not res[0].ok
    assert "não resolve" in (res[0].detail or "")


def test_one_bad_source_does_not_hide_the_good_ones() -> None:
    res = _run(_Client(falham={"ruim"}), ["boa", "ruim", "outra"])
    assert [r.ok for r in res] == [True, False, True]


def test_timeout_degrades_to_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    """Diagnóstico que trava por rede é pior que diagnóstico incompleto."""
    monkeypatch.setattr("garimpo.tools.doctor._RESOLVE_TIMEOUT_S", 0.05)
    res = _run(_Client(trava={"lenta"}), ["lenta"])
    assert res[0].ok and res[0].warn and "timeout" in (res[0].detail or "")


def test_no_sources_means_no_extra_calls() -> None:
    client = _Client()
    assert _run(client, []) == []
    assert client.chamadas == 0

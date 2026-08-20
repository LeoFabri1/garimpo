"""A bad source must not take the whole run down.

Sources are user-typed handles. A typo, a renamed channel or a private group
the account never joined are all routine, and Telethon signals them with a
raw exception from get_entity.
"""

from __future__ import annotations

import pytest

from garimpo.ingest.base import SourceRef
from garimpo.ingest.clients.fake_client import FakeMTProtoClient
from garimpo.ingest.listener import NoSourcesResolvedError, resolve_sources


class PickyClient(FakeMTProtoClient):
    """Resolves only the usernames it was told about."""

    def __init__(self, known: set[str]) -> None:
        super().__init__()
        self.known = known
        self._next_id = 1000

    async def resolve_source(self, source: SourceRef) -> SourceRef:
        if source.username not in self.known:
            raise ValueError(f"No user has \"{source.username}\" as username")
        self._next_id += 1
        return SourceRef(
            tg_id=self._next_id, username=source.username, parser=source.parser
        )


@pytest.mark.asyncio
async def test_one_bad_source_does_not_sink_the_good_ones() -> None:
    client = PickyClient(known={"promobit_hardware"})
    resolved = await resolve_sources(
        client,
        [
            SourceRef(username="promobit_hardware", parser="promobit"),
            SourceRef(username="grupo_que_nao_existe", parser="generic"),
        ],
    )
    assert [s.username for s in resolved] == ["promobit_hardware"]


@pytest.mark.asyncio
async def test_all_sources_failing_raises_actionable_error() -> None:
    client = PickyClient(known=set())
    with pytest.raises(NoSourcesResolvedError) as err:
        await resolve_sources(
            client, [SourceRef(username="tanto_faz", parser="generic")]
        )

    msg = str(err.value)
    assert "tanto_faz" in msg, "must name the source that failed"
    assert "sources:" in msg, "must point at the config key to fix"
    assert "membro" in msg, "must mention the unjoined-group case"


@pytest.mark.asyncio
async def test_healthy_sources_pass_through_with_real_tg_ids() -> None:
    client = PickyClient(known={"a", "b"})
    resolved = await resolve_sources(
        client,
        [SourceRef(username="a", parser="generic"), SourceRef(username="b")],
    )
    assert len(resolved) == 2
    assert all(s.tg_id is not None for s in resolved)

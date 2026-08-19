"""Map config sources → ingest SourceRef."""

from __future__ import annotations

from garimpo.ingest.base import SourceRef
from garimpo.settings import Settings
from garimpo.settings import SourceRef as CfgSource


def sources_from_settings(settings: Settings) -> list[SourceRef]:
    out: list[SourceRef] = []
    for s in settings.sources:
        if not s.enabled:
            continue
        out.append(_from_cfg(s))
    return out


def _from_cfg(s: CfgSource) -> SourceRef:
    return SourceRef(
        tg_id=s.id,
        username=s.username.lstrip("@") if s.username else None,
        parser=s.parser,
    )

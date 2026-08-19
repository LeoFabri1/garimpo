"""Fast triage: discard ~95% of volume with near-zero false negatives."""

from __future__ import annotations

import re

TRIAGE = re.compile(
    r"(rtx|gtx|radeon|geforce|arc\s?[ab]\d|rx\s?\d{3,4}|"
    r"placa\s+de\s+v[íi]deo|gpu)",
    re.IGNORECASE,
)


def passes_triage(text: str) -> bool:
    return TRIAGE.search(text) is not None

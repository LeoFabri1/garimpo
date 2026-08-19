"""Fast triage: discard ~95% of volume with near-zero false negatives."""

from __future__ import annotations

import re

# Keep broad enough for configured categories (gpu / notebook / cpu).
TRIAGE = re.compile(
    r"("
    r"rtx|gtx|radeon|geforce|arc\s?[ab]\d|rx\s?\d{3,4}|"
    r"placa\s+de\s+v[íi]deo|gpu|"
    r"notebook|laptop|ultrabook|"
    r"ryzen|threadripper|core\s*i[3579]|intel\s*i[3579]|\bi[3579]-\d"
    r")",
    re.IGNORECASE,
)


def passes_triage(text: str) -> bool:
    return TRIAGE.search(text) is not None

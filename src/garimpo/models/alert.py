"""Scored offer and alert level."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from garimpo.models.offer import Offer


class Level(StrEnum):
    CRITICAL = "critical"
    NORMAL = "normal"
    IGNORE = "ignore"


@dataclass(frozen=True, slots=True)
class ScoredOffer:
    offer: Offer
    level: Level
    percentile: float | None
    baseline: float | None
    min_90d: float | None
    n_samples: int
    price_per_pt: float | None
    reason: str
    rule_name: str | None = None

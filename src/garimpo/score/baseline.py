"""Baseline with exponential time decay (half-life)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from garimpo.score.stats import WeightedPoint, weighted_mad, weighted_median


@dataclass(frozen=True, slots=True)
class HistoryPoint:
    price: float
    observed_at: datetime
    excluded: bool = False


@dataclass(frozen=True, slots=True)
class Baseline:
    kind: str  # ok | insufficient
    n: int
    median: float | None = None
    mad: float | None = None
    min_90d: float | None = None


def compute_baseline(
    history: list[HistoryPoint],
    now: datetime,
    *,
    window_days: int = 90,
    half_life_days: float = 21.0,
    min_samples: int = 12,
) -> Baseline:
    pts: list[tuple[HistoryPoint, float]] = []
    for p in history:
        if p.excluded:
            continue
        age_days = (now - p.observed_at).total_seconds() / 86400.0
        if age_days < 0 or age_days > window_days:
            continue
        pts.append((p, age_days))

    if len(pts) < min_samples:
        return Baseline(kind="insufficient", n=len(pts))

    weighted = [
        WeightedPoint(price=p.price, weight=0.5 ** (age / half_life_days))
        for p, age in pts
    ]
    med = weighted_median(weighted)
    mad = weighted_mad(weighted, med)
    min_90d = min(p.price for p, _ in pts)
    return Baseline(kind="ok", n=len(pts), median=med, mad=mad, min_90d=min_90d)


def mark_outliers(
    history: list[HistoryPoint],
    baseline: Baseline,
    *,
    mad_threshold: float = 3.0,
) -> list[HistoryPoint]:
    """Return history with extreme points flagged excluded (does not mutate input)."""
    if baseline.kind != "ok" or baseline.median is None or baseline.mad is None:
        return list(history)
    out: list[HistoryPoint] = []
    for p in history:
        if p.excluded:
            out.append(p)
            continue
        if baseline.mad == 0:
            is_outlier = p.price != baseline.median
        else:
            is_outlier = abs(p.price - baseline.median) > mad_threshold * baseline.mad
        if is_outlier:
            out.append(
                HistoryPoint(
                    price=p.price,
                    observed_at=p.observed_at,
                    excluded=True,
                )
            )
        else:
            out.append(p)
    return out

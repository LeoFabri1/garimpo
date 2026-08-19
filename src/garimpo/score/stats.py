"""Robust statistics for price baselines."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class WeightedPoint:
    price: float
    weight: float


def weighted_median(points: list[WeightedPoint]) -> float:
    if not points:
        raise ValueError("empty points")
    ordered = sorted(points, key=lambda p: p.price)
    total = sum(p.weight for p in ordered)
    if total <= 0:
        return ordered[len(ordered) // 2].price
    halfway = total / 2.0
    acc = 0.0
    for p in ordered:
        acc += p.weight
        if acc >= halfway:
            return p.price
    return ordered[-1].price


def weighted_mad(points: list[WeightedPoint], median: float) -> float:
    deviations = [
        WeightedPoint(price=abs(p.price - median), weight=p.weight) for p in points
    ]
    return weighted_median(deviations)

"""Deterministic alert level — never from an LLM."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from garimpo.models.alert import Level, ScoredOffer
from garimpo.models.catalog import Product
from garimpo.models.offer import Offer
from garimpo.score.baseline import HistoryPoint, compute_baseline
from garimpo.score.explain import explain
from garimpo.score.perf import price_per_perf

# Below this, an offer is a suspected mis-parse: it neither alerts nor is
# recorded as a price observation. Shared so the two checks cannot drift.
MIN_CONFIDENCE = 0.8


@dataclass(frozen=True, slots=True)
class WatchRule:
    name: str
    max_price: float
    models: frozenset[str] | None = None
    min_perf: float | None = None
    max_price_per_perf: float | None = None
    critical_percentile: float = 0.03
    normal_percentile: float = 0.15
    min_store_trust_critical: float = 0.9
    stores_exclude: frozenset[str] = frozenset()
    silent: bool | None = None
    always_alert: bool = False
    siren: bool = False


def match_rule(
    model_key: str,
    perf: float,
    rules: list[WatchRule],
    store: str | None = None,
) -> WatchRule | None:
    """First rule whose model/perf/store filters all accept the offer."""
    for rule in rules:
        if rule.models is not None and model_key not in rule.models:
            continue
        if rule.min_perf is not None and perf < rule.min_perf:
            continue
        if store and store in rule.stores_exclude:
            continue
        return rule
    return None


def weighted_percentile_rank(
    history: list[HistoryPoint],
    price: float,
    now: datetime,
    *,
    window_days: int = 90,
    half_life_days: float = 21.0,
) -> float:
    """Fraction of weighted mass strictly below `price`."""
    weighted: list[tuple[float, float]] = []
    for p in history:
        if p.excluded:
            continue
        age = (now - p.observed_at).total_seconds() / 86400.0
        if age < 0 or age > window_days:
            continue
        w = 0.5 ** (age / half_life_days)
        weighted.append((p.price, w))
    total = sum(w for _, w in weighted)
    if total <= 0:
        return 1.0
    below = sum(w for pr, w in weighted if pr < price)
    return below / total


def score_offer(
    offer: Offer,
    *,
    product: Product,
    history: list[HistoryPoint],
    rule: WatchRule,
    now: datetime,
    store_trust: float = 1.0,
    min_samples: int = 12,
    window_days: int = 90,
    half_life_days: float = 21.0,
) -> ScoredOffer:
    ppt = price_per_perf(offer.price.amount, product)

    if offer.confidence < MIN_CONFIDENCE:
        return _ignore(offer, rule, f"confidence < {MIN_CONFIDENCE}", ppt, n=len(history))

    if float(offer.price.amount) > rule.max_price:
        return _ignore(offer, rule, "above max_price", ppt, n=len(history))

    if rule.models is not None and offer.model_key not in rule.models:
        return _ignore(offer, rule, "model not in rule", ppt, n=len(history))

    if offer.store and offer.store in rule.stores_exclude:
        return _ignore(offer, rule, "store excluded by rule", ppt, n=len(history))

    if rule.min_perf is not None and product.perf < rule.min_perf:
        return _ignore(offer, rule, "below perf_tier", ppt, n=len(history))

    if rule.max_price_per_perf is not None and ppt is not None and ppt > rule.max_price_per_perf:
        return _ignore(offer, rule, "above max_price_per_perf", ppt, n=len(history))

    baseline = compute_baseline(
        history,
        now,
        window_days=window_days,
        half_life_days=half_life_days,
        min_samples=min_samples,
    )

    if baseline.kind == "insufficient":
        level = Level.NORMAL if float(offer.price.amount) <= rule.max_price else Level.IGNORE
        reason = f"baixa confiança (histórico curto, n={baseline.n})"
        return ScoredOffer(
            offer=offer,
            level=level,
            percentile=None,
            baseline=None,
            min_90d=None,
            n_samples=baseline.n,
            price_per_pt=ppt,
            reason=reason,
            rule_name=rule.name,
            rule_silent=rule.silent,
        rule_always_alert=rule.always_alert,
        rule_siren=rule.siren,
        )

    pct = weighted_percentile_rank(
        history,
        float(offer.price.amount),
        now,
        window_days=window_days,
        half_life_days=half_life_days,
    )
    if baseline.median is None:  # pragma: no cover - compute_baseline invariant
        raise RuntimeError("baseline ok sem mediana")

    if pct <= rule.critical_percentile and store_trust >= rule.min_store_trust_critical:
        level = Level.CRITICAL
    elif pct <= rule.normal_percentile:
        level = Level.NORMAL
    elif rule.always_alert:
        # max_price was already checked above: under the ceiling is enough.
        level = Level.NORMAL
    else:
        level = Level.IGNORE

    reason = explain(
        price=float(offer.price.amount),
        percentile=pct,
        baseline=baseline,
        window_days=window_days,
    )
    return ScoredOffer(
        offer=offer,
        level=level,
        percentile=pct,
        baseline=baseline.median,
        min_90d=baseline.min_90d,
        n_samples=baseline.n,
        price_per_pt=ppt,
        reason=reason,
        rule_name=rule.name,
        rule_silent=rule.silent,
        rule_always_alert=rule.always_alert,
        rule_siren=rule.siren,
    )


def _ignore(
    offer: Offer,
    rule: WatchRule,
    reason: str,
    ppt: float | None,
    *,
    n: int,
) -> ScoredOffer:
    return ScoredOffer(
        offer=offer,
        level=Level.IGNORE,
        percentile=None,
        baseline=None,
        min_90d=None,
        n_samples=n,
        price_per_pt=ppt,
        reason=reason,
        rule_name=rule.name,
        rule_silent=rule.silent,
        rule_always_alert=rule.always_alert,
        rule_siren=rule.siren,
    )


def sanity_confidence_for_price(amount: Decimal, product: Product) -> float:
    """Helper mirroring generic parser MSRP gate."""
    if product.msrp_brl is None:
        return 1.0
    msrp = Decimal(str(product.msrp_brl))
    if amount < msrp * Decimal("0.3") or amount > msrp * Decimal("2.0"):
        return 0.5
    return 1.0

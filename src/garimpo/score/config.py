"""Single source of truth for turning config into a WatchRule.

`run` and `simulate` must build rules identically, otherwise calibration
measures thresholds the daemon never applies.
"""

from __future__ import annotations

import re

from garimpo.catalog.index import ModelIndex
from garimpo.score.rules import WatchRule
from garimpo.settings import Settings, WatchRuleConfig

_PERF_TIER = re.compile(r">=\s*([\d.]+)")


def resolve_model_keys(models: list[str] | None, index: ModelIndex) -> frozenset[str] | None:
    if not models:
        return None
    resolved: set[str] = set()
    for name in models:
        hit = index.resolve(name)
        resolved.add(hit.model_key if hit else name.lower().replace(" ", "_"))
    return frozenset(resolved)


def parse_perf_tier(perf_tier: str | None) -> float | None:
    if not perf_tier:
        return None
    match = _PERF_TIER.search(perf_tier)
    return float(match.group(1)) if match else None


def watch_rule_from_config(
    cfg: WatchRuleConfig,
    index: ModelIndex,
    settings: Settings,
) -> WatchRule:
    critical = settings.alerts.critical
    return WatchRule(
        name=cfg.name or "default",
        max_price=cfg.max_price,
        models=resolve_model_keys(cfg.models, index),
        min_perf=parse_perf_tier(cfg.perf_tier),
        max_price_per_perf=cfg.max_price_per_perf,
        critical_percentile=critical.percentile,
        normal_percentile=settings.alerts.normal.percentile,
        min_store_trust_critical=(
            critical.min_store_trust if critical.min_store_trust is not None else 0.9
        ),
        stores_exclude=frozenset(cfg.stores_exclude),
        silent=cfg.silent,
        always_alert=cfg.always_alert,
        siren=cfg.siren,
    )


def watch_rules_from_settings(settings: Settings, index: ModelIndex) -> list[WatchRule]:
    return [watch_rule_from_config(cfg, index, settings) for cfg in settings.watch]

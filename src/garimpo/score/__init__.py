"""Scoring: baseline, rules, explanations."""

from garimpo.score.baseline import Baseline, HistoryPoint, compute_baseline, mark_outliers
from garimpo.score.config import (
    parse_perf_tier,
    resolve_model_keys,
    watch_rule_from_config,
    watch_rules_from_settings,
)
from garimpo.score.rules import WatchRule, match_rule, score_offer

__all__ = [
    "Baseline",
    "HistoryPoint",
    "WatchRule",
    "compute_baseline",
    "mark_outliers",
    "match_rule",
    "parse_perf_tier",
    "resolve_model_keys",
    "score_offer",
    "watch_rule_from_config",
    "watch_rules_from_settings",
]

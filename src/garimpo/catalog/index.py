"""Inverted alias index: longest alias first, negative_aliases as safety net."""

from __future__ import annotations

import re
from dataclasses import dataclass

from rapidfuzz import fuzz, process

from garimpo.models.catalog import Catalog, Product


@dataclass(frozen=True, slots=True)
class ResolveResult:
    model_key: str
    confidence: float
    matched_alias: str | None
    method: str  # exact | fuzzy


class ModelIndex:
    def __init__(self, catalog: Catalog) -> None:
        self._catalog = catalog
        pairs: list[tuple[str, str]] = []
        for key, product in catalog.products.items():
            for alias in product.aliases:
                pairs.append((alias, key))
        pairs.sort(key=lambda p: len(p[0]), reverse=True)
        self._pairs = pairs
        self._alias_list = [a for a, _ in pairs]
        self._patterns = [(_alias_pattern(a), a, k) for a, k in pairs]

    def get(self, model_key: str) -> Product | None:
        return self._catalog.products.get(model_key)

    def resolve(self, text: str, *, fuzzy_cutoff: int = 88) -> ResolveResult | None:
        lowered = text.lower()

        for pattern, alias, key in self._patterns:
            if pattern.search(lowered) is None:
                continue
            product = self._catalog.products[key]
            if _hits_negative(lowered, alias, product.negative_aliases):
                continue
            return ResolveResult(
                model_key=key,
                confidence=1.0,
                matched_alias=alias,
                method="exact",
            )

        if not self._alias_list:
            return None

        match = process.extractOne(
            lowered,
            self._alias_list,
            scorer=fuzz.partial_ratio,
            score_cutoff=fuzzy_cutoff,
        )
        if match is None:
            return None
        alias, score, _idx = match
        if not _digits_agree(lowered, alias):
            return None
        key = next(k for a, k in self._pairs if a == alias)
        product = self._catalog.products[key]
        if _hits_negative(lowered, alias, product.negative_aliases):
            return None
        return ResolveResult(
            model_key=key,
            confidence=float(score) / 100.0,
            matched_alias=alias,
            method="fuzzy",
        )


def _alias_pattern(alias: str) -> re.Pattern[str]:
    """Match an alias whose spaces the channel may have dropped.

    Channels write the same card three ways — "RTX 4060", "RTX4060",
    "rtx 4060" — and a plain substring test only finds the spelling someone
    remembered to type into the catalog. Nine products had no glued alias, so
    "notebook rtx4060 i7" reached the exact pass unmatched and was decided by
    the fuzzy scorer instead: right key, 0.97 confidence, on the same
    `partial_ratio` that `_digits_agree` below exists to police. Replaying the
    whole message archive, 20 real listings took that route.

    So each space in the alias becomes optional. The text itself is never
    touched: squashing it would destroy the boundaries we need, because
    "notebook rtx4060 i7" squashed reads "notebookrtx4060i7" and the "i" of
    "i7" then looks like part of the model name.

    The lookahead is what keeps the suffix honest: an alias may run into a
    digit ("rtx5070ti16gb" is one card) but never into a letter, so
    "rtx 5070 titan" no longer answers for the alias "rtx 5070 ti" — which it
    did, as a plain substring, long before spaces became optional.

    `negative_aliases` deliberately do NOT come through here. The lookahead
    makes matching stricter, which is the safe direction for an alias and the
    dangerous one for a negative: with it, the negative "5600g" stopped
    seeing "Ryzen 5 5600GT" and twenty of those landed on `ryzen_5_5600`.
    A negative stays a greedy substring.
    """
    body = r"\s*".join(re.escape(part) for part in alias.split())
    return re.compile(body + r"(?![a-z])")


_MODEL_NUMBER = re.compile(r"\d{3,4}")


def _digits_agree(text: str, alias: str) -> bool:
    """A fuzzy match may not invent a different model number.

    GPU names are identifiers, not prose: one digit separates two products.
    `partial_ratio` scores "geforce rtx 2060 super" against the alias
    "rtx 5060" at 93.75 — above the cutoff, and above MIN_CONFIDENCE, so the
    wrong price reached the baseline and fired alerts. Worse, a card missing
    from the catalog (RX 9060 XT) got snapped onto its nearest neighbour
    instead of being left unmatched.

    So: whatever number the alias claims must actually appear in the text.
    """
    wanted = set(_MODEL_NUMBER.findall(alias))
    if not wanted:
        return True
    found = set(_MODEL_NUMBER.findall(text))
    return bool(wanted & found)


def _hits_negative(text: str, matched_alias: str, negatives: tuple[str, ...]) -> bool:
    for neg in negatives:
        if neg not in text:
            continue
        if neg == matched_alias:
            return True
        # Longer / more specific form present → wrong product
        # e.g. matched "rtx 5070" but text has "5070 ti"
        if len(neg) > len(matched_alias):
            return True
        # Class / form factors (notebook vs desktop, Ti/XT/Super)
        if any(
            tag in neg
            for tag in (
                " ti",
                "ti",
                " xt",
                "xt",
                " gre",
                "gre",
                " super",
                "super",
                "notebook",
                "laptop",
                "desktop",
                # Máquina montada não é peça avulsa. Um "PC Gamer Pichau com
                # RTX 5060" a R$ 4.800 entrava no baseline da placa como se
                # fosse a placa — e chegou a virar alerta.
                "pc gamer",
                "computador",
                "all in one",
            )
        ):
            return True
        # Sibling SKU token present (e.g. matched 4060 alias but text also has 4070)
        if neg not in matched_alias:
            return True
    return False

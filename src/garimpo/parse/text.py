"""Text normalization for triage, hashing, and matching."""

from __future__ import annotations

import re
import unicodedata

# Zero-width and BOM used to bypass filters
_ZERO_WIDTH = re.compile(r"[\u200b\u200c\u200d\ufeff]")

# Emoji / symbols → space (not empty: PLACA🔥DE must not become PLACADE)
_EMOJI = re.compile(
    "["
    "\U0001f300-\U0001faff"
    "\U00002700-\U000027bf"
    "\U0001f000-\U0001f02f"
    "\U00002600-\U000026ff"
    "\U0000fe00-\U0000fe0f"
    "\U0001f900-\U0001f9ff"
    "]+",
    flags=re.UNICODE,
)

# Some channels drop the "R$" and let the emoji be the marker: "💵6,991".
# Must run before _EMOJI erases it, or the price has no marker left.
_MONEY_EMOJI = re.compile(r"[\U0001f4b0\U0001f4b5\U0001f4b8]\ufe0f?\s*(?=\d)")

_TG_MARKDOWN = re.compile(r"(\*\*|__|\|\||`)")
_MULTI_SPACE = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    """Clean message text for parsing.

    Callers that match against the catalog should lowercase explicitly.
    """
    s = unicodedata.normalize("NFKC", text)
    s = _ZERO_WIDTH.sub("", s)
    s = _MONEY_EMOJI.sub(" R$ ", s)
    s = _EMOJI.sub(" ", s)
    s = _TG_MARKDOWN.sub("", s)
    s = _MULTI_SPACE.sub(" ", s).strip()
    return s


def normalize_for_hash(text: str) -> str:
    """Stable hash input: cleaned, lowercase, no whitespace."""
    s = normalize_text(text).lower()
    return re.sub(r"\s+", "", s)


def normalize_for_match(text: str) -> str:
    return normalize_text(text).lower()

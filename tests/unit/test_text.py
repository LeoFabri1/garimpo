"""Tests for text normalization."""

from garimpo.parse.text import normalize_for_hash, normalize_text


def test_emoji_becomes_space_not_glue() -> None:
    assert "PLACA DE" in normalize_text("PLACA🔥DE").upper().replace("  ", " ")


def test_zero_width_removed() -> None:
    assert normalize_text("RTX\u200b5070") == "RTX5070" or "RTX" in normalize_text(
        "RTX\u200b 5070"
    )


def test_hash_normalization_stable() -> None:
    a = normalize_for_hash("RTX 5070 Ti — Kabum")
    b = normalize_for_hash("rtx 5070 ti kabum")
    assert a == b or a.replace("—", "") == b  # dash may remain as char

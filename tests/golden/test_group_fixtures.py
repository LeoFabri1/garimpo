"""Golden parser checks across group fixtures."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from garimpo.catalog import ModelIndex, load_gpu_catalog
from garimpo.models.raw import RawMessage
from garimpo.parse.groups import ParserRegistry

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "messages"
GROUPS = ("generic", "promobit", "pelando", "hardmob", "gatry")


def _collect_cases() -> list[tuple[str, Path, Path | None]]:
    cases: list[tuple[str, Path, Path | None]] = []
    for group in GROUPS:
        group_dir = FIXTURE_ROOT / group
        if not group_dir.is_dir():
            continue
        for path in sorted(group_dir.glob("*.txt")):
            expected = group_dir / "expected" / f"{path.stem}.json"
            cases.append((group, path, expected if expected.is_file() else None))
    return cases


CASES = _collect_cases()


@pytest.fixture(scope="module")
def registry() -> ParserRegistry:
    return ParserRegistry(ModelIndex(load_gpu_catalog()))


@pytest.mark.parametrize(
    ("group", "path", "expected_path"),
    CASES,
    ids=[f"{g}/{p.name}" for g, p, _ in CASES],
)
def test_group_fixture_golden(
    registry: ParserRegistry,
    group: str,
    path: Path,
    expected_path: Path | None,
) -> None:
    text = path.read_text(encoding="utf-8")
    msg = RawMessage(
        source_id=1,
        tg_msg_id=1,
        text=text,
        has_media=False,
        received_at=datetime.now(UTC),
        parser_hint=None if group == "generic" else group,
    )
    offer = registry.parse(msg)
    assert offer is not None, f"failed to parse {group}/{path.name}"

    if expected_path is None:
        # Legacy generic fixtures without sidecar: at least resolve a known GPU.
        assert offer.model_key
        assert offer.price.amount > 0
        return

    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    assert offer.model_key == expected["model_key"]
    assert offer.price.amount == Decimal(expected["price"])
    if "store" in expected:
        assert offer.store == expected["store"]
    if "coupon" in expected:
        assert offer.coupon is not None
        assert offer.coupon.code == expected["coupon"]
    assert offer.confidence >= float(expected.get("min_confidence", 0.8))


def test_parse_rate_above_95(registry: ParserRegistry) -> None:
    assert CASES, "no fixtures found"
    ok = 0
    for group, path, _ in CASES:
        text = path.read_text(encoding="utf-8")
        msg = RawMessage(
            source_id=1,
            tg_msg_id=1,
            text=text,
            has_media=False,
            received_at=datetime.now(UTC),
            parser_hint=None if group == "generic" else group,
        )
        if registry.parse(msg) is not None:
            ok += 1
    rate = ok / len(CASES)
    assert rate >= 0.95, f"parse rate {rate:.0%} < 95% ({ok}/{len(CASES)})"

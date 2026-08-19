"""Quiet hours helper tests."""

from datetime import datetime

from garimpo.alert.quiet import in_quiet_hours


def test_quiet_wraps_midnight() -> None:
    assert in_quiet_hours(datetime(2026, 8, 1, 23, 30), [23, 8]) is True
    assert in_quiet_hours(datetime(2026, 8, 1, 3, 0), [23, 8]) is True
    assert in_quiet_hours(datetime(2026, 8, 1, 12, 0), [23, 8]) is False


def test_quiet_same_day_window() -> None:
    assert in_quiet_hours(datetime(2026, 8, 1, 14, 0), [13, 17]) is True
    assert in_quiet_hours(datetime(2026, 8, 1, 18, 0), [13, 17]) is False


def test_quiet_none() -> None:
    assert in_quiet_hours(datetime(2026, 8, 1, 3, 0), None) is False

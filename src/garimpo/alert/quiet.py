"""Quiet hours: defer normal alerts; critical always passes (DESIGN §12.3)."""

from __future__ import annotations

from datetime import datetime, time


def in_quiet_hours(now: datetime, quiet: list[int] | None) -> bool:
    """quiet = [start_hour, end_hour), e.g. [23, 8] means 23:00–08:00."""
    if not quiet or len(quiet) != 2:
        return False
    start_h, end_h = quiet
    hour = now.hour
    if start_h == end_h:
        return False
    if start_h < end_h:
        return start_h <= hour < end_h
    # wraps midnight
    return hour >= start_h or hour < end_h


def quiet_end_today(now: datetime, quiet: list[int]) -> datetime:
    """Next local datetime when quiet hours end (end_h:00)."""
    end_h = quiet[1]
    candidate = datetime.combine(now.date(), time(hour=end_h))
    if now.hour >= end_h and quiet[0] > quiet[1]:
        # after midnight segment ended? if currently in quiet wrapping
        if now.hour >= quiet[0]:
            from datetime import timedelta

            candidate = candidate + timedelta(days=1)
    elif now >= candidate and quiet[0] < quiet[1]:
        from datetime import timedelta

        candidate = candidate + timedelta(days=1)
    return candidate

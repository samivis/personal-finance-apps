from __future__ import annotations
import datetime as dt
from decimal import Decimal


def week_window_for(d: dt.date) -> tuple[dt.date, dt.date]:
    start = d - dt.timedelta(days=(d.weekday() + 1) % 7)
    return start, start + dt.timedelta(days=6)


def previous_week_window_for(week_start: dt.date) -> tuple[dt.date, dt.date]:
    return week_window_for(week_start - dt.timedelta(days=1))


def tab_name_for_week(start: dt.date, end: dt.date) -> str:
    return f"{start.month}/{start.day}-{end.month}/{end.day}"


def sheet_display_date(d: dt.date) -> str:
    return f"{d.month}/{d.day}/{d.year}"


def weeks_in_range(start: dt.date, end: dt.date) -> list[dt.date]:
    """Return each distinct week_start (Sunday) touched by [start, end]."""
    out: list[dt.date] = []
    ws, _ = week_window_for(start)
    while ws <= end:
        out.append(ws)
        ws = ws + dt.timedelta(days=7)
    return out


def compute_weekly_budget(base: Decimal, prev_total_left: Decimal | None) -> Decimal:
    if prev_total_left is None:
        return base
    return max(Decimal("0"), base + prev_total_left)

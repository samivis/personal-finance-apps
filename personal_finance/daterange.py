from __future__ import annotations
import datetime as dt
import re


def week_window_for(d: dt.date) -> tuple[dt.date, dt.date]:
    # Sunday..Saturday. weekday() Mon=0..Sun=6 -> days since Sunday = (weekday()+1)%7
    start = d - dt.timedelta(days=(d.weekday() + 1) % 7)
    return start, start + dt.timedelta(days=6)


def _parse_one_date(token: str, today: dt.date) -> dt.date:
    token = token.strip().lower()
    if token == "today":
        return today
    if token == "yesterday":
        return today - dt.timedelta(days=1)
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d"):
        try:
            d = dt.datetime.strptime(token, fmt).date()
            if fmt == "%m/%d":
                d = d.replace(year=today.year)
            return d
        except ValueError:
            pass
    raise ValueError(f"Unrecognized date: {token!r}")


def parse_range(text: str, today: dt.date) -> tuple[dt.date, dt.date]:
    t = text.strip().lower()
    week_start, _ = week_window_for(today)

    if t == "today":
        return today, today
    if t == "this week":
        return week_start, today
    if t == "last week":
        prev_end = week_start - dt.timedelta(days=1)
        return week_window_for(prev_end)
    if t in ("yesterday to today", "yesterday"):
        return today - dt.timedelta(days=1), today
    if t == "last sunday to this sunday":
        # most recent Sunday (week_start) through the following Sunday
        return week_start, week_start + dt.timedelta(days=7)

    # Explicit range: "A to B" or "A..B"
    parts = re.split(r"\s*(?:to|\.\.)\s*", t)
    if len(parts) == 2:
        start = _parse_one_date(parts[0], today)
        end = _parse_one_date(parts[1], today)
        if end < start:
            raise ValueError(f"End date {end} is before start date {start}")
        return start, end
    if len(parts) == 1:
        d = _parse_one_date(parts[0], today)
        return d, d

    raise ValueError(f"Could not parse date range: {text!r}")

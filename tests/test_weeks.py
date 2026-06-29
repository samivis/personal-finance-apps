# tests/test_weeks.py
import datetime as dt
from decimal import Decimal
from personal_finance.weeks import (
    week_window_for, previous_week_window_for, tab_name_for_week,
    sheet_display_date, weeks_in_range, compute_weekly_budget,
)

def test_week_window_sunday_start():
    assert week_window_for(dt.date(2026, 6, 24)) == (dt.date(2026, 6, 21), dt.date(2026, 6, 27))

def test_tab_name_format():
    assert tab_name_for_week(dt.date(2026, 6, 1), dt.date(2026, 6, 7)) == "6/1-6/7"

def test_sheet_display_date():
    assert sheet_display_date(dt.date(2026, 6, 5)) == "6/5/2026"

def test_weeks_in_range_spans_two_weeks():
    ws = weeks_in_range(dt.date(2026, 6, 20), dt.date(2026, 6, 22))
    assert ws == [dt.date(2026, 6, 14), dt.date(2026, 6, 21)]

def test_compute_weekly_budget_rollover():
    assert compute_weekly_budget(Decimal("200"), Decimal("30")) == Decimal("230")
    assert compute_weekly_budget(Decimal("200"), Decimal("-250")) == Decimal("0")
    assert compute_weekly_budget(Decimal("200"), None) == Decimal("200")

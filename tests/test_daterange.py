# tests/test_daterange.py
import datetime as dt
import pytest
from personal_finance.daterange import parse_range

TODAY = dt.date(2026, 6, 24)  # a Wednesday

@pytest.mark.parametrize("text,expected", [
    ("today", (dt.date(2026, 6, 24), dt.date(2026, 6, 24))),
    ("yesterday to today", (dt.date(2026, 6, 23), dt.date(2026, 6, 24))),
    ("this week", (dt.date(2026, 6, 21), dt.date(2026, 6, 24))),          # Sun..today
    ("last week", (dt.date(2026, 6, 14), dt.date(2026, 6, 20))),          # prior full Sun-Sat
    ("last Sunday to this Sunday", (dt.date(2026, 6, 21), dt.date(2026, 6, 28))),
    ("6/1 to 6/15", (dt.date(2026, 6, 1), dt.date(2026, 6, 15))),
    ("2026-06-01..2026-06-15", (dt.date(2026, 6, 1), dt.date(2026, 6, 15))),
    ("6/10", (dt.date(2026, 6, 10), dt.date(2026, 6, 10))),
])
def test_parse_range(text, expected):
    assert parse_range(text, TODAY) == expected

def test_parse_range_invalid():
    with pytest.raises(ValueError):
        parse_range("sometime last autumn", TODAY)

def test_end_before_start_raises():
    with pytest.raises(ValueError):
        parse_range("6/15 to 6/1", TODAY)

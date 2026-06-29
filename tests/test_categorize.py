# tests/test_categorize.py
from decimal import Decimal
from personal_finance.categorize import (
    classify, normalize_category, pretty_description, is_expense,
    is_ignored, to_dropdown_category, DROPDOWN_CATEGORY_VALUES,
)

def test_classify_fixed():
    assert classify("TIDY CLEANING")[1] == "fixed"

def test_classify_variable_food():
    cat, kind = classify("TST* SIDECAR DOUGHNUTS")
    assert (cat, kind) == ("food", "variable")

def test_classify_unknown():
    assert classify("ZZZ MYSTERY VENDOR")[0] == "unknown"

def test_pretty_description():
    assert pretty_description("WHOLEFDS MON 10250") == "Whole Foods"

def test_is_expense_checking_negative():
    assert is_expense("Chase Main Checking", Decimal("-50")) is True
    assert is_expense("Chase Main Checking", Decimal("50")) is False

def test_is_expense_credit_positive():
    assert is_expense("Chase Sapphire Reserve", Decimal("50")) is True

def test_dropdown_category_blank_for_unknown():
    assert to_dropdown_category("unknown") == ""
    assert to_dropdown_category("food") == "Food"
    assert to_dropdown_category("food") in DROPDOWN_CATEGORY_VALUES

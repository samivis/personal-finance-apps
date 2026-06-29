# tests/test_teller.py
import datetime as dt
from decimal import Decimal
from personal_finance.teller import _row_to_txn

def test_row_to_txn_in_range():
    row = {"id": "txn_1", "account_id": "acc_1", "date": "2026-06-10",
           "amount": "12.50", "description": "Kreation", "type": "card", "status": "posted"}
    t = _row_to_txn(row, "Chase Sapphire Reserve", "label")
    assert t.id == "txn_1"
    assert t.amount == Decimal("12.50")
    assert t.date == dt.date(2026, 6, 10)
    assert t.account_name == "Chase Sapphire Reserve"

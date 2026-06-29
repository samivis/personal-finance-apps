# tests/test_orchestrator.py
import datetime as dt
from decimal import Decimal
from personal_finance.teller import Txn
from personal_finance.orchestrator import group_by_week

def mk(id_, d):
    return Txn(id=id_, account_id="a", account_name="Chase Sapphire Reserve",
               date=d, amount=Decimal("5"), description="Kreation", type="card", status="posted", source="x")

def test_group_by_week_splits_across_weeks():
    txns = [mk("a", dt.date(2026,6,20)), mk("b", dt.date(2026,6,22))]
    groups = group_by_week(txns)
    assert set(groups.keys()) == {dt.date(2026,6,14), dt.date(2026,6,21)}
    assert [t.id for t in groups[dt.date(2026,6,21)]] == ["b"]

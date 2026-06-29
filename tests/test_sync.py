# tests/test_sync.py
import datetime as dt
from decimal import Decimal
from personal_finance.teller import Txn
from personal_finance.sync import parse_teller_id_note, row_for_txn, sync_week

def mk(id_, desc, amt, d):
    return Txn(id=id_, account_id="a", account_name="Chase Sapphire Reserve",
               date=d, amount=Decimal(amt), description=desc, type="card", status="posted", source="x")

def test_parse_note():
    assert parse_teller_id_note("foo\nteller-id:txn_9\nbar") == "txn_9"
    assert parse_teller_id_note("") == ""

def test_row_for_txn():
    row, note = row_for_txn(mk("txn_1", "TST* SIDECAR DOUGHNUTS", "6.50", dt.date(2026,6,24)))
    assert row[0] == "Sidecar Doughnuts"  # pretty name
    assert row[2] == "Variable"        # Type
    assert row[3] == "Food"            # Category
    assert row[4] == "6/24/2026"       # Date
    assert note == "teller-id:txn_1"

class FakeClient:
    def __init__(self, tabs, reads):
        self._tabs = list(tabs); self.reads = reads
        self.ensured = []; self.appended = []
    def list_tabs(self): return self._tabs
    def read(self, rng): return self.reads.get(rng, ([], []))
    def ensure_tab(self, tab, wb, f): self.ensured.append((tab, wb)); self._tabs.append(tab); return True
    def append(self, tab, start, rows, notes): self.appended.append((tab, start, rows, notes)); return len(rows)

def test_sync_week_creates_tab_and_appends_new():
    # base budget from Monthly Budget!C20 = 200, no prior tab -> budget 200
    reads = {"'Monthly Budget'!C20": ([["200"]], [[""]])}
    client = FakeClient(tabs=["Monthly Budget"], reads=reads)
    txns = [mk("txn_1", "TST* SIDECAR DOUGHNUTS", "6.50", dt.date(2026,6,24))]
    tab, added, updated = sync_week(client, dt.date(2026,6,21), txns)
    assert tab == "6/21-6/27"
    assert added == 1 and updated == 0
    assert client.ensured and client.ensured[0][1] == 200.0

def test_sync_week_dedupes_by_note():
    reads = {
        "'Monthly Budget'!C20": ([["200"]], [[""]]),
        "'6/21-6/27'!A2:F2000": ([["Sidecar Doughnuts", "$6.50", "Variable", "Food", "6/24/2026", ""]],
                                  [["teller-id:txn_1"]]),
    }
    client = FakeClient(tabs=["Monthly Budget", "6/21-6/27"], reads=reads)
    txns = [mk("txn_1", "TST* SIDECAR DOUGHNUTS", "6.50", dt.date(2026,6,24))]
    tab, added, updated = sync_week(client, dt.date(2026,6,21), txns)
    assert added == 0  # already present by note

def test_sync_week_distinct_teller_id_same_content_not_dropped():
    # txn_1 already synced (has teller-id note); txn_2 has same content but different id -> must be added
    reads = {
        "'Monthly Budget'!C20": ([["200"]], [[""]]),
        "'6/21-6/27'!A2:F2000": (
            [["Sidecar Doughnuts", "6.5", "Variable", "Food", "6/24/2026", ""]],
            [["teller-id:txn_1"]],
        ),
    }
    client = FakeClient(tabs=["Monthly Budget", "6/21-6/27"], reads=reads)
    txns = [mk("txn_2", "TST* SIDECAR DOUGHNUTS", "6.50", dt.date(2026, 6, 24))]
    tab, added, updated = sync_week(client, dt.date(2026, 6, 21), txns)
    assert added == 1  # distinct teller-id must not be swallowed by content-match

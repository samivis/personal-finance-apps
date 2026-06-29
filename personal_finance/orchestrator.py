from __future__ import annotations
import datetime as dt
from collections import defaultdict

from .teller import Txn, fetch_transactions
from .weeks import week_window_for
from .sync import sync_week
from .daterange import parse_range


def group_by_week(txns: list[Txn]) -> dict[dt.date, list[Txn]]:
    groups: dict[dt.date, list[Txn]] = defaultdict(list)
    for t in txns:
        ws, _ = week_window_for(t.date)
        groups[ws].append(t)
    return dict(groups)


def run(range_text, today, client, config_path, cert_path, key_path) -> dict:
    start, end = parse_range(range_text, today)
    txns, errors = fetch_transactions(start, end, config_path, cert_path, key_path)
    per_tab = []
    for ws, week_txns in sorted(group_by_week(txns).items()):
        tab, added, updated = sync_week(client, ws, week_txns)
        per_tab.append({"tab": tab, "added": added, "updated": updated})
    return {"range": [start.isoformat(), end.isoformat()], "per_tab": per_tab, "errors": errors}

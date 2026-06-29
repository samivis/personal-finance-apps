from __future__ import annotations
import datetime as dt
from decimal import Decimal

from .categorize import (classify, normalize_category, pretty_description,
                         is_expense, is_ignored, to_dropdown_category,
                         is_canceled, KNOWN_FIXED)
from .teller import Txn, ACCOUNT_ALLOWLIST
from .weeks import (week_window_for, previous_week_window_for, tab_name_for_week,
                    sheet_display_date, compute_weekly_budget)

TOTAL_LEFT_FORMULA = '=I9-SUMIF(C:C,"Variable",B:B)'


def parse_teller_id_note(note: str) -> str:
    for line in str(note or "").splitlines():
        line = line.strip()
        if line.startswith("teller-id:"):
            return line[len("teller-id:"):].strip()
    return ""


def _type_cat_notes(t: Txn) -> tuple[str, str, str]:
    cat, kind = classify(t.description)
    cat = normalize_category(cat)
    notes = []
    if cat == "startup":
        notes.append("startup expense — move to business card")
    if is_canceled(t.description):
        notes.append("canceled sub still charged")
    amt = abs(t.amount)
    if amt > 100 and kind != "fixed":
        notes.append(">$100 non-fixed")
    if cat == "unknown":
        notes.append("needs categorization")
    type_str = kind.capitalize() if kind in ("fixed", "variable") else ""
    return type_str, to_dropdown_category(cat), "; ".join(notes)


def row_for_txn(t: Txn) -> tuple[list, str]:
    type_str, cat, notes = _type_cat_notes(t)
    amt = float(abs(t.amount))
    row = [pretty_description(t.description), amt, type_str, cat, sheet_display_date(t.date), notes]
    return row, f"teller-id:{t.id}"


def base_weekly_budget(client) -> Decimal:
    values, _ = client.read("'Monthly Budget'!C20")
    raw = values[0][0] if values and values[0] else ""
    cleaned = str(raw).replace("$", "").replace(",", "").strip()
    try:
        return Decimal(cleaned)
    except Exception:
        raise RuntimeError("Could not read base weekly budget from 'Monthly Budget'!C20")


def prev_total_left(client, week_start: dt.date) -> Decimal | None:
    prev_start, prev_end = previous_week_window_for(week_start)
    prev_tab = tab_name_for_week(prev_start, prev_end)
    if prev_tab not in client.list_tabs():
        return None
    values, _ = client.read(f"'{prev_tab}'!H9:I10")
    for row in values:
        if len(row) >= 2 and str(row[0]).strip() == "Total Left":
            try:
                return Decimal(str(row[1]).replace("$", "").replace(",", "").strip())
            except Exception:
                return None
    return None


def _amount_key(v) -> str:
    s = str(v or "").strip().replace("$", "").replace(",", "")
    try:
        return f"{Decimal(s):.2f}"
    except Exception:
        return s


def sync_week(client, week_start: dt.date, week_txns: list[Txn]) -> tuple[str, int, int]:
    _, week_end = week_window_for(week_start)
    tab = tab_name_for_week(week_start, week_end)

    # filter to this week's real expenses
    seen_ids: set[str] = set()
    week: list[Txn] = []
    for t in sorted(week_txns, key=lambda x: (x.date, x.account_name, x.id)):
        if t.id in seen_ids:
            continue
        if not (week_start <= t.date <= week_end):
            continue
        if t.status not in {"posted", "complete", "pending"}:
            continue
        if t.account_name not in ACCOUNT_ALLOWLIST:
            continue
        if is_ignored(t.description) or not is_expense(t.account_name, t.amount):
            continue
        seen_ids.add(t.id)
        week.append(t)
    if not week:
        return tab, 0, 0

    # create tab with rollover budget if missing
    if tab not in client.list_tabs():
        base = base_weekly_budget(client)
        budget = compute_weekly_budget(base, prev_total_left(client, week_start))
        client.ensure_tab(tab, float(budget), TOTAL_LEFT_FORMULA)

    # read existing rows + notes for dedup
    values, notes = client.read(f"'{tab}'!A2:F2000")
    id_to_row: dict[str, int] = {}
    content_rows: dict[tuple, list[int]] = {}
    last_row = 1
    for i, row in enumerate(values, start=2):
        if row and str(row[0]).strip():
            last_row = i
        key = (str(row[0]).strip() if len(row) > 0 else "",
               _amount_key(row[1] if len(row) > 1 else ""),
               str(row[4]).strip() if len(row) > 4 else "")
        note = ""
        idx = i - 2
        if idx < len(notes) and notes[idx]:
            note = notes[idx][0] if notes[idx] else ""
        tid = parse_teller_id_note(note)
        if tid:
            id_to_row[tid] = i
        else:
            content_rows.setdefault(key, []).append(i)

    new_rows: list[list] = []
    new_notes: list[str] = []
    for t in week:
        if t.id in id_to_row:
            continue  # already present
        row, note = row_for_txn(t)
        key = (str(row[0]).strip(), _amount_key(row[1]), str(row[4]).strip())
        if len(content_rows.get(key, [])) >= 1:
            continue  # content match (note missing) — skip to avoid dup
        new_rows.append(row)
        new_notes.append(note)

    added = 0
    if new_rows:
        start = last_row + 1
        added = client.append(tab, start, new_rows, new_notes)
    return tab, added, 0

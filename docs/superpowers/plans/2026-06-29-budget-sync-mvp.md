# Budget Sync MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A skill that asks for a date range, pulls bank transactions for that range from all connected accounts, and syncs them into the correct Sun–Sat weekly tab of a Google Sheet (creating the tab with rollover budget if needed, categorizing, never duplicating) — all via the Apps Script webhook.

**Architecture:** A small Python package (`personal_finance/`) of focused modules: a flexible date-range parser, a categorizer (ported verbatim from the legacy Mini tracker), week/rollover helpers (ported), a Teller fetcher (ported), and a sheet client that POSTs to an extended Apps Script webhook. An orchestrator wires them together. No `gog`/OAuth anywhere.

**Tech Stack:** Python 3.14 stdlib only (no third-party deps). Google Apps Script (`.gs`) for the in-sheet webhook. `pytest` (or stdlib `unittest`) for tests.

## Global Constraints

- Python stdlib only — no third-party packages. (verbatim: "Python 3.14 stdlib only")
- Weeks run **Sunday → Saturday**.
- Tab name format: `M/D-M/D` (no zero padding), e.g. `6/1-6/7`.
- Sheet columns: A Description, B Cost, C Type, D Category, E Date (`m/d/yyyy`), F Notes, G Feelings (**never written**).
- Dedup key: cell note `teller-id:<id>` on column A.
- Category dropdown values exactly: `Food`, `Transportation`, `Shopping`, `Other`, `Health`. Type values exactly: `Fixed`, `Variable`.
- `Total Left` formula verbatim: `=I9-SUMIF(C:C,"Variable",B:B)`.
- Legacy source to port from (read-only reference): `~/Desktop/projects/_mini-finance-import/personal-finance-apps/bin/daily_budget_tracker.py`.
- Secrets/personal data must never be committed (existing `.gitignore` covers it).

---

### Task 1: Date-range parser

**Files:**
- Create: `personal_finance/__init__.py` (empty)
- Create: `personal_finance/daterange.py`
- Test: `tests/test_daterange.py`

**Interfaces:**
- Produces: `parse_range(text: str, today: datetime.date) -> tuple[date, date]`. Raises `ValueError` on unparseable input. `today` is injected for testability.
- Helper produced: `week_window_for(d: date) -> tuple[date, date]` (Sun–Sat) — re-exported here for the parser's week math; the canonical copy lives in Task 3 and both must stay identical.

- [ ] **Step 1: Write failing tests**

```python
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
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `python3 -m pytest tests/test_daterange.py -v`
Expected: FAIL (module not found / `parse_range` undefined).

- [ ] **Step 3: Implement `personal_finance/daterange.py`**

```python
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
```

- [ ] **Step 4: Run tests, verify pass**

Run: `python3 -m pytest tests/test_daterange.py -v`
Expected: PASS (all parametrized cases + error cases).

- [ ] **Step 5: Commit**

```bash
git add personal_finance/__init__.py personal_finance/daterange.py tests/test_daterange.py
git commit -m "feat: flexible date-range parser (Sun-Sat aware)"
```

---

### Task 2: Categorizer (port verbatim)

**Files:**
- Create: `personal_finance/categorize.py`
- Test: `tests/test_categorize.py`

**Interfaces:**
- Produces: `classify(description: str) -> tuple[str, str | None]`, `normalize_category(c: str) -> str`, `pretty_description(raw: str) -> str`, `is_expense(account_name: str, amount: Decimal) -> bool`, `is_ignored(description: str) -> bool`, `to_dropdown_category(fine: str) -> str`, `is_canceled(description: str) -> bool`, and module constants `DROPDOWN_CATEGORY_VALUES`, `DROPDOWN_TYPE_VALUES`, `KNOWN_FIXED`, `STARTUP_KEYWORDS`, `CANCELED_KEYWORDS`. Plus `load_vendor_rules(rules_path: Path) -> None`.
- Note: `is_expense` is refactored from the legacy `is_expense(txn)` to take `(account_name, amount)` so it has no `Txn` dependency.

- [ ] **Step 1: Write failing tests**

```python
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
```

- [ ] **Step 2: Run tests, verify fail**

Run: `python3 -m pytest tests/test_categorize.py -v`
Expected: FAIL (module not found).

- [ ] **Step 3: Implement `personal_finance/categorize.py`**

Copy these symbols **verbatim** from the legacy source `~/Desktop/projects/_mini-finance-import/personal-finance-apps/bin/daily_budget_tracker.py` (lines noted): `MONTHLY_*` budget constants are NOT needed here — skip them. Copy: `DROPDOWN_TYPE_VALUES`, `DROPDOWN_CATEGORY_VALUES`, `DROPDOWN_CATEGORY`, `to_dropdown_category` (108-112), `KNOWN_FIXED` (114-126), `STARTUP_KEYWORDS` (128-137), `CANCELED_KEYWORDS` (139-154), `DEFAULT_FIXED_RULES` (171-193), `DEFAULT_VARIABLE_RULES` (196-296), `normalize` (405-406), the module-level `FIXED_VENDOR_RULES`/`VARIABLE_RULES`/`IGNORED_KEYWORDS`/`DEFAULT_IGNORED_KEYWORDS` (410-416), `load_vendor_rules` (419-441, but change its signature to take `rules_path: Path` directly instead of deriving from a state path), `is_ignored` (444-446), `classify` (449-460), `normalize_category` (463-466), `VENDOR_DISPLAY` (472-519), `_POS_PREFIXES` (522), `pretty_description` (525-586), `is_canceled` (589-591).

Then add this refactored `is_expense` (replacing the legacy `Txn`-based one):

```python
from decimal import Decimal

def is_expense(account_name: str, amount: Decimal) -> bool:
    # Checking: only money OUT (negative) is an expense. Credit cards: positive = charge.
    if account_name == "Chase Main Checking":
        return amount < 0
    return amount > 0
```

`load_vendor_rules` new signature:

```python
from pathlib import Path

def load_vendor_rules(rules_path: Path) -> None:
    if not rules_path.exists():
        return
    try:
        rules = json.loads(rules_path.read_text())
    except (json.JSONDecodeError, OSError):
        return
    user_fixed = [(r["match"].lower(), r["category"]) for r in rules.get("fixed", [])]
    user_variable = [(r["match"].lower(), r["category"]) for r in rules.get("variable", [])]
    FIXED_VENDOR_RULES[:0] = user_fixed
    VARIABLE_RULES[:0] = user_variable
    for k in rules.get("startup_keywords", []):
        if k not in STARTUP_KEYWORDS:
            STARTUP_KEYWORDS.append(k.lower())
    for k in rules.get("canceled_keywords", []):
        if k not in CANCELED_KEYWORDS:
            CANCELED_KEYWORDS.append(k.lower())
    for k in rules.get("ignored", []):
        IGNORED_KEYWORDS.append(k.lower())
```

Add `import json` at the top.

- [ ] **Step 4: Run tests, verify pass**

Run: `python3 -m pytest tests/test_categorize.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add personal_finance/categorize.py tests/test_categorize.py
git commit -m "feat: categorizer ported from legacy tracker (Txn-free is_expense)"
```

---

### Task 3: Week + rollover helpers

**Files:**
- Create: `personal_finance/weeks.py`
- Test: `tests/test_weeks.py`

**Interfaces:**
- Produces: `week_window_for(d) -> (date,date)`, `previous_week_window_for(week_start) -> (date,date)`, `tab_name_for_week(start, end) -> str`, `sheet_display_date(d) -> str`, `weeks_in_range(start, end) -> list[date]` (returns each week_start touched by the range).
- Produces: `compute_weekly_budget(base: Decimal, prev_total_left: Decimal | None) -> Decimal` — `max(0, base + prev_total_left)`, or `base` when `prev_total_left is None`.

- [ ] **Step 1: Write failing tests**

```python
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
```

- [ ] **Step 2: Run tests, verify fail**

Run: `python3 -m pytest tests/test_weeks.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `personal_finance/weeks.py`**

```python
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
```

- [ ] **Step 4: Run tests, verify pass**

Run: `python3 -m pytest tests/test_weeks.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add personal_finance/weeks.py tests/test_weeks.py
git commit -m "feat: week-window, tab-name, and rollover helpers"
```

---

### Task 4: Teller fetch

**Files:**
- Create: `personal_finance/teller.py`
- Test: `tests/test_teller.py`

**Interfaces:**
- Produces dataclass `Txn(id, account_id, account_name, date, amount: Decimal, description, type, status, source)`.
- Produces `fetch_transactions(start: date, end: date, config_path: Path, cert_path: Path, key_path: Path) -> tuple[list[Txn], list[str]]` — returns `(txns, errors)`. `errors` holds per-account failure strings (disconnected enrollments etc.); never raises for a single bad account.
- Consumes: `ACCOUNT_ALLOWLIST` (define here, copy from legacy lines 156-161).
- **Cert portability:** ignore the per-connection `certificatePath`/`privateKeyPath` in config; always use the passed `cert_path`/`key_path` (the caller passes `~/.bank-mcp/keys/teller/*`).

- [ ] **Step 1: Write failing test (pure parsing, no network)**

```python
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
```

- [ ] **Step 2: Run test, verify fail**

Run: `python3 -m pytest tests/test_teller.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `personal_finance/teller.py`**

```python
from __future__ import annotations
import base64
import datetime as dt
import http.client
import json
import ssl
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

ACCOUNT_ALLOWLIST = {
    "Chase Main Checking",
    "Chase Sapphire Reserve",
    "Chase Freedom Unlimited",
    "American Express Delta SkyMiles® Reserve Card",
}


@dataclass
class Txn:
    id: str
    account_id: str
    account_name: str
    date: dt.date
    amount: Decimal
    description: str
    type: str
    status: str
    source: str


def _row_to_txn(row: dict, account_name: str, label: str) -> Txn:
    return Txn(
        id=row["id"],
        account_id=row.get("account_id", ""),
        account_name=account_name,
        date=dt.date.fromisoformat(row["date"]),
        amount=Decimal(str(row["amount"])),
        description=row.get("description", ""),
        type=row.get("type", ""),
        status=row.get("status", ""),
        source=label,
    )


def _fetch_json(req, ctx, attempts=4):
    last = None
    for i in range(attempts):
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=60) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError:
            raise
        except (http.client.IncompleteRead, urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last = e
            if i == attempts - 1:
                break
            time.sleep(2 ** (i + 1))
    raise RuntimeError(f"Teller fetch failed after {attempts} attempts: {last!r}")


def fetch_transactions(start: dt.date, end: dt.date, config_path: Path,
                       cert_path: Path, key_path: Path) -> tuple[list[Txn], list[str]]:
    cfg = json.loads(Path(config_path).read_text())
    ctx = ssl.create_default_context()
    ctx.load_cert_chain(str(cert_path), str(key_path))
    txns: list[Txn] = []
    errors: list[str] = []
    for conn in cfg.get("connections", []):
        label = conn.get("label", "")
        c2 = conn.get("config", {})
        token = c2.get("accessToken")
        auth = "Basic " + base64.b64encode((token + ":").encode()).decode()
        for acc in c2.get("accounts", []):
            name = acc.get("name", "")
            if name not in ACCOUNT_ALLOWLIST:
                continue
            base_url = f"https://api.teller.io/accounts/{acc['uid']}/transactions"
            from_id = None
            done = False
            for _page in range(20):
                if done:
                    break
                url = base_url + "?count=50" + (f"&from_id={from_id}" if from_id else "")
                req = urllib.request.Request(url, headers={"Authorization": auth})
                try:
                    rows = _fetch_json(req, ctx)
                except (RuntimeError, urllib.error.HTTPError) as exc:
                    detail = str(exc)
                    if isinstance(exc, urllib.error.HTTPError):
                        try:
                            body = json.loads(exc.read())
                            detail = body.get("error", {}).get("message", str(exc))
                        except Exception:
                            pass
                    errors.append(f"{name} ({label}): {detail}")
                    break
                if not rows:
                    break
                for row in rows:
                    d = dt.date.fromisoformat(row["date"])
                    if d < start:
                        done = True
                        break
                    if d <= end:
                        txns.append(_row_to_txn(row, name, label))
                if len(rows) < 50:
                    break
                from_id = rows[-1]["id"]
    return txns, errors
```

- [ ] **Step 4: Run test, verify pass**

Run: `python3 -m pytest tests/test_teller.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add personal_finance/teller.py tests/test_teller.py
git commit -m "feat: Teller fetch with date-range filter and per-account error capture"
```

---

### Task 5: Extend the Apps Script webhook

**Files:**
- Modify: `apps_script_webhook.gs`
- Test: manual (documented verification steps; Apps Script can't be unit-tested locally).

**Interfaces:**
- `doPost(e)` routes on `body.action`: `append`, `list_tabs`, `read`, `ensure_tab`. All require `body.secret === SHARED_SECRET`. Returns JSON `{ok: true, ...}` or `{ok:false, error}`.
- `read` `{range}` → `{ok, values, notes}` where `notes` is a 2D array aligned to `values` rows (note text or "").
- `ensure_tab` `{tab, headers, weekly_budget, total_left_formula}` → creates+scaffolds if missing; `{ok, created: bool}`.
- `append` `{tab, start_row, rows, notes}` → writes rows in A:F, sets col-A note per row; `{ok, appended}`.

- [ ] **Step 1: Replace `apps_script_webhook.gs` contents**

```javascript
var SHARED_SECRET = 'CHANGE_ME_TO_A_LONG_RANDOM_STRING';
var GID = 1509499529;
var HEADERS = ["Description", "Cost", "Type", "Category", "Date", "Notes", "Feelings"];
var TYPE_VALUES = ["Fixed", "Variable"];
var CATEGORY_VALUES = ["Food", "Transportation", "Shopping", "Other", "Health"];

function doPost(e) {
  try {
    var body = JSON.parse(e.postData.contents);
    if (body.secret !== SHARED_SECRET) return json_({ ok: false, error: 'bad secret' });
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    switch (body.action) {
      case 'list_tabs': return json_({ ok: true, tabs: ss.getSheets().map(function (s) { return s.getName(); }) });
      case 'read': return read_(ss, body);
      case 'ensure_tab': return ensureTab_(ss, body);
      case 'append': return append_(ss, body);
      default: return appendLegacy_(ss, body); // back-compat: {rows:[...]} -> default tab
    }
  } catch (err) {
    return json_({ ok: false, error: String(err) });
  }
}

function tabByName_(ss, name) {
  var t = ss.getSheetByName(name);
  return t;
}

function read_(ss, body) {
  var rng = ss.getRange(body.range);
  var values = rng.getValues();
  var notes = rng.getNotes();
  return json_({ ok: true, values: values, notes: notes });
}

function ensureTab_(ss, body) {
  var name = body.tab;
  if (ss.getSheetByName(name)) return json_({ ok: true, created: false });
  var sheet = ss.insertSheet(name);
  sheet.getRange(1, 1, 1, HEADERS.length).setValues([HEADERS]).setFontWeight('bold');
  sheet.setFrozenRows(1);
  sheet.getRange('H9:I9').setValues([['Weekly Budget', body.weekly_budget]]);
  sheet.getRange('H10').setValue('Total Left');
  sheet.getRange('I10').setFormula(body.total_left_formula);
  // dropdowns on C (Type) and D (Category), rows 2..1000
  sheet.getRange(2, 3, 999, 1).setDataValidation(
    SpreadsheetApp.newDataValidation().requireValueInList(TYPE_VALUES, true).build());
  sheet.getRange(2, 4, 999, 1).setDataValidation(
    SpreadsheetApp.newDataValidation().requireValueInList(CATEGORY_VALUES, true).build());
  return json_({ ok: true, created: true });
}

function append_(ss, body) {
  var sheet = ss.getSheetByName(body.tab);
  if (!sheet) return json_({ ok: false, error: 'tab not found: ' + body.tab });
  var rows = body.rows || [];
  if (!rows.length) return json_({ ok: true, appended: 0 });
  var start = body.start_row;
  sheet.getRange(start, 1, rows.length, rows[0].length).setValues(rows);
  if (body.notes) {
    for (var i = 0; i < body.notes.length; i++) {
      if (body.notes[i]) sheet.getRange(start + i, 1).setNote(body.notes[i]);
    }
  }
  sheet.getRange(start, 2, rows.length, 1).setNumberFormat('"$"#,##0.00'); // Cost
  sheet.getRange(start, 5, rows.length, 1).setNumberFormat('m/d/yyyy');    // Date
  return json_({ ok: true, appended: rows.length });
}

function appendLegacy_(ss, body) {
  var rows = body.rows || [];
  var sheet = null, tabs = ss.getSheets();
  for (var i = 0; i < tabs.length; i++) { if (tabs[i].getSheetId() === GID) { sheet = tabs[i]; break; } }
  if (!sheet) sheet = ss.getSheets()[0];
  if (!rows.length) return json_({ ok: true, appended: 0 });
  var start = sheet.getLastRow() + 1;
  sheet.getRange(start, 1, rows.length, rows[0].length).setValues(rows);
  return json_({ ok: true, appended: rows.length });
}

function json_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}
```

- [ ] **Step 2: Manual verification (documented; user redeploys)**

Document in commit message: user pastes into the sheet's Apps Script editor, sets `SHARED_SECRET` to the real value, and redeploys via **Manage deployments → edit → New version** (same URL). Verify with:
```bash
python3 - <<'PY'
import json, urllib.request, pathlib
cfg = json.loads(pathlib.Path.home().joinpath('.config/daily-budget/webhook.json').read_text())
def call(payload):
    payload['secret'] = cfg['secret']
    req = urllib.request.Request(cfg['url'], data=json.dumps(payload).encode(), headers={'Content-Type':'application/json'})
    return json.loads(urllib.request.urlopen(req, timeout=30).read())
print(call({'action':'list_tabs'}))
PY
```
Expected: `{'ok': True, 'tabs': [...]}`.

- [ ] **Step 3: Commit**

```bash
git add apps_script_webhook.gs
git commit -m "feat: webhook gains list_tabs/read/ensure_tab/append actions (back-compat default)"
```

---

### Task 6: Sheet client (Python → webhook)

**Files:**
- Create: `personal_finance/sheet_client.py`
- Test: `tests/test_sheet_client.py`

**Interfaces:**
- Produces class `SheetClient(url, secret, http_post=urllib_post)` where `http_post(url, payload_dict) -> dict` is injectable for tests.
- Methods: `list_tabs() -> list[str]`, `read(range_) -> tuple[list[list], list[list]]` (values, notes), `ensure_tab(tab, weekly_budget: float, total_left_formula: str) -> bool`, `append(tab, start_row: int, rows: list[list], notes: list[str]) -> int`.
- Raises `RuntimeError` on `{ok:false}` or transport error.

- [ ] **Step 1: Write failing tests (fake transport)**

```python
# tests/test_sheet_client.py
from personal_finance.sheet_client import SheetClient

class FakePost:
    def __init__(self, responses): self.responses = responses; self.calls = []
    def __call__(self, url, payload):
        self.calls.append(payload)
        return self.responses[payload["action"]]

def test_list_tabs():
    post = FakePost({"list_tabs": {"ok": True, "tabs": ["6/1-6/7"]}})
    c = SheetClient("u", "s", http_post=post)
    assert c.list_tabs() == ["6/1-6/7"]
    assert post.calls[0]["secret"] == "s"

def test_append_returns_count():
    post = FakePost({"append": {"ok": True, "appended": 2}})
    c = SheetClient("u", "s", http_post=post)
    assert c.append("6/1-6/7", 5, [["a"],["b"]], ["teller-id:x", ""]) == 2

def test_raises_on_not_ok():
    post = FakePost({"list_tabs": {"ok": False, "error": "bad secret"}})
    c = SheetClient("u", "s", http_post=post)
    try:
        c.list_tabs(); assert False
    except RuntimeError as e:
        assert "bad secret" in str(e)
```

- [ ] **Step 2: Run tests, verify fail**

Run: `python3 -m pytest tests/test_sheet_client.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `personal_finance/sheet_client.py`**

```python
from __future__ import annotations
import json
import urllib.request


def urllib_post(url: str, payload: dict) -> dict:
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


class SheetClient:
    def __init__(self, url: str, secret: str, http_post=urllib_post):
        self.url = url
        self.secret = secret
        self._post = http_post

    def _call(self, payload: dict) -> dict:
        payload["secret"] = self.secret
        try:
            res = self._post(self.url, payload)
        except Exception as e:
            raise RuntimeError(f"webhook transport error: {e!r}")
        if not res.get("ok"):
            raise RuntimeError(f"webhook rejected {payload.get('action')}: {res.get('error')}")
        return res

    def list_tabs(self) -> list[str]:
        return self._call({"action": "list_tabs"})["tabs"]

    def read(self, range_: str) -> tuple[list[list], list[list]]:
        res = self._call({"action": "read", "range": range_})
        return res.get("values", []), res.get("notes", [])

    def ensure_tab(self, tab: str, weekly_budget: float, total_left_formula: str) -> bool:
        return self._call({"action": "ensure_tab", "tab": tab,
                           "weekly_budget": weekly_budget,
                           "total_left_formula": total_left_formula})["created"]

    def append(self, tab: str, start_row: int, rows: list[list], notes: list[str]) -> int:
        return self._call({"action": "append", "tab": tab, "start_row": start_row,
                           "rows": rows, "notes": notes})["appended"]
```

- [ ] **Step 4: Run tests, verify pass**

Run: `python3 -m pytest tests/test_sheet_client.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add personal_finance/sheet_client.py tests/test_sheet_client.py
git commit -m "feat: SheetClient wrapping the webhook actions (injectable transport)"
```

---

### Task 7: Sync engine (dedup + per-week write)

**Files:**
- Create: `personal_finance/sync.py`
- Test: `tests/test_sync.py`

**Interfaces:**
- Consumes: `Txn` (Task 4), `SheetClient` (Task 6), categorizer (Task 2), weeks helpers (Task 3).
- Produces: `parse_teller_id_note(note: str) -> str`, `row_for_txn(t: Txn) -> tuple[list, str]` (the A–F row + the col-A note), `base_weekly_budget(client) -> Decimal` (reads `'Monthly Budget'!C20`), `prev_total_left(client, week_start) -> Decimal | None` (reads prior tab `H9:I10`), and `sync_week(client, week_start, week_txns) -> tuple[str,int,int]` (tab, added, updated).
- `TOTAL_LEFT_FORMULA = '=I9-SUMIF(C:C,"Variable",B:B)'`.

- [ ] **Step 1: Write failing tests (fake client)**

```python
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
    assert row[0] == "Sidecar Doughnuts" or row[0]  # pretty name
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
```

- [ ] **Step 2: Run tests, verify fail**

Run: `python3 -m pytest tests/test_sync.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `personal_finance/sync.py`**

```python
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
    return Decimal(str(raw).replace("$", "").replace(",", "").strip())


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
        content_rows.setdefault(key, []).append(i)
        note = ""
        idx = i - 2
        if idx < len(notes) and notes[idx]:
            note = notes[idx][0] if notes[idx] else ""
        tid = parse_teller_id_note(note)
        if tid:
            id_to_row[tid] = i

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
```

- [ ] **Step 4: Run tests, verify pass**

Run: `python3 -m pytest tests/test_sync.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add personal_finance/sync.py tests/test_sync.py
git commit -m "feat: per-week sync engine with note-based dedup and rollover tab creation"
```

---

### Task 8: Orchestrator + skill wiring

**Files:**
- Create: `budget_sync.py` (repo-root CLI entry)
- Modify: skill file `~/Desktop/projects/context/personal/.claude/skills/daily-budget-update/SKILL.md` (point it at the new entry; private repo, not this one)
- Test: `tests/test_orchestrator.py`

**Interfaces:**
- Produces `run(range_text: str, today: date, client, config_path, cert_path, key_path) -> dict` returning `{range, per_tab: [...], errors: [...]}`. Pure-ish: client + paths injected.
- CLI: `python3 budget_sync.py "<range>"` — if range omitted, prompts interactively. Loads webhook config from `~/.config/daily-budget/webhook.json`, Teller paths from `~/.bank-mcp`.

- [ ] **Step 1: Write failing test**

```python
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
```

- [ ] **Step 2: Run test, verify fail**

Run: `python3 -m pytest tests/test_orchestrator.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `personal_finance/orchestrator.py`**

```python
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
```

- [ ] **Step 4: Run test, verify pass**

Run: `python3 -m pytest tests/test_orchestrator.py -v`
Expected: PASS.

- [ ] **Step 5: Implement `budget_sync.py` CLI (no test — thin glue)**

```python
#!/usr/bin/env python3
import json
import sys
from pathlib import Path

from personal_finance.orchestrator import run
from personal_finance.sheet_client import SheetClient
from personal_finance.categorize import load_vendor_rules
import datetime as dt

HOME = Path.home()
WEBHOOK = HOME / ".config" / "daily-budget" / "webhook.json"
CONFIG = HOME / ".bank-mcp" / "config.json"
CERT = HOME / ".bank-mcp" / "keys" / "teller" / "certificate.pem"
KEY = HOME / ".bank-mcp" / "keys" / "teller" / "private_key.pem"
VENDOR_RULES = Path(__file__).resolve().parent.parent / "context" / "personal" / "data" / "finance" / "vendor-rules.json"


def main() -> int:
    range_text = sys.argv[1] if len(sys.argv) > 1 else input(
        "Date range (e.g. 'last week', 'yesterday to today', '6/1 to 6/15'): ").strip()
    if VENDOR_RULES.exists():
        load_vendor_rules(VENDOR_RULES)
    cfg = json.loads(WEBHOOK.read_text())
    client = SheetClient(cfg["url"], cfg["secret"])
    result = run(range_text, dt.date.today(), client, CONFIG, CERT, KEY)
    print(f"Synced {result['range'][0]} → {result['range'][1]}")
    for pt in result["per_tab"]:
        print(f"  {pt['tab']}: +{pt['added']} new, {pt['updated']} updated")
    for e in result["errors"]:
        print(f"  [skipped] {e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 6: Run full test suite**

Run: `python3 -m pytest tests/ -v`
Expected: PASS (all tasks' tests green).

- [ ] **Step 7: Commit**

```bash
git add personal_finance/orchestrator.py budget_sync.py tests/test_orchestrator.py
git commit -m "feat: orchestrator + CLI entry; group-by-week and per-tab sync"
```

- [ ] **Step 8: Update the skill (private repo) + manual live smoke**

Edit `~/Desktop/projects/context/personal/.claude/skills/daily-budget-update/SKILL.md` so "How to run" asks for a date range and runs `python3 ~/Desktop/projects/personal-finance-apps/budget_sync.py "<range>"`. Then live smoke (after webhook redeploy): `python3 budget_sync.py "last week"` and confirm rows land in the correct weekly tab. Commit the skill change in the context repo.

---

## Notes for the implementer

- Retire the old `daily_budget_update.py` only AFTER `budget_sync.py` is verified live (separate cleanup commit).
- The `examples/merchant-categories.example.json` already documents the map shape; no change needed.
- Keep `apps_script_webhook.gs` back-compatible (`appendLegacy_`) so the old runner doesn't break mid-migration.

# Budget Sync MVP — Design

_Date: 2026-06-29_

## Goal

A skill that, when run, asks for a date range, pulls bank transactions for that range
from all connected accounts, and writes them into the correct Sun–Sat weekly tab of a
Google Sheet — creating the tab (with rollover budget) if needed, categorizing each
transaction, and never duplicating. All sheet writes go through an Apps Script webhook
(no `gog`/OAuth), so nothing expires on a 7-day clock.

## Non-goals (deferred)

Manual-entry queue, Amex repair tooling, markdown daily reports, Slack/Notion delivery.
These exist in the legacy Mini tracker and can be ported later.

## User flow

1. User runs the skill.
2. Skill asks for a date range. Accepted forms:
   - Presets: `last week`, `this week`, `yesterday to today`, `last Sunday to this Sunday`,
     `today`.
   - Explicit: `6/1 to 6/15`, `2026-06-01..2026-06-15`, a single date (treated as that day).
3. Skill resolves the input to a concrete `start_date`→`end_date` and echoes it back
   ("Pulling Jun 1 – Jun 15…").
4. It fetches, categorizes, and syncs; then prints a per-tab summary
   (`6/1-6/7: +4 new, 1 updated`).

## Components

### 1. Date-range parser (`daterange.py`)
- Input: a free-text string. Output: `(start: date, end: date)`.
- Weeks run Sunday→Saturday. "last week" = the most recent completed Sun–Sat; "this week"
  = current Sun–Sat to today.
- Pure function, fully unit-tested against the accepted forms. Raises a clear error on
  unparseable input.

### 2. Teller fetch (ported from Mini tracker)
- Reads `~/.bank-mcp/config.json` (nested `connections[].config` schema: accessToken,
  certificatePath, privateKeyPath, accounts).
- mTLS to `api.teller.io`, paginates (`count=50`, `from_id`), stops past the range.
- Disconnected/MFA enrollments are skipped and reported, not fatal.
- **Cert-path portability:** the MacBook must use cert paths that resolve here. Resolve
  cert/key from a fixed local path (`~/.bank-mcp/keys/teller/*`) rather than trusting the
  embedded config path (which may point at the Mini's home).

### 3. Categorizer (ported verbatim from Mini tracker)
- `classify()` (fixed rules → variable rules → startup → unknown), `normalize_category()`,
  `pretty_description()`, `is_expense()`, `is_ignored()`, vendor display names, and
  `vendor-rules.json` loading. Folds into the sheet's Type (Fixed/Variable) and the 5
  Category dropdown values; unknown/startup left blank with a Notes signal.

### 4. Week bucketing + rollover (ported from Mini tracker)
- `week_window_for`, `previous_week_window_for`, `tab_name_for_week` (`M/D-M/D`).
- On new-tab creation: `weekly_budget = base + previous_week_total_left`, floored at 0,
  where `base` comes from `'Monthly Budget'!C20` and `previous_week_total_left` is read
  from the prior tab's `H9:I10`. `Total Left` (I10) stays the live formula
  `=I9-SUMIF(C:C,"Variable",B:B)`.

### 5. Sheet client (`sheet_client.py`) — talks to the webhook
Replaces the entire `gog`/OAuth layer. POSTs JSON `{secret, action, ...}` to the webhook.
Actions:
- `list_tabs` → `[names]`
- `read` `{range}` → `{values, notes}` (notes for dedup; values for content match + rollover)
- `ensure_tab` `{tab, headers, weekly_budget, total_left_formula, dropdowns}` → creates +
  scaffolds the tab if missing (idempotent)
- `append` `{tab, start_row, rows, notes, number_formats}` → writes A–F rows, sets the
  per-row `teller-id:<id>` note on col A, applies currency/date number formats

### 6. Apps Script webhook (`apps_script_webhook.gs`) — extended
Add `doPost` action routing for the above. Apps Script runs inside the sheet as the
owner, so it natively does `insertSheet`, `setNote`, `setFormula`, `setDataValidation`,
`setNumberFormat` — no token, no expiry.

### 7. Orchestrator (`budget_sync.py`) + skill
`parse range → fetch → categorize → group by week → for each week: ensure_tab → dedupe →
append`. The `daily-budget-update` skill invokes it and asks for the range first.

## Sheet contract (unchanged from existing sheet)

Columns: A Description (pretty), B Cost, C Type, D Category, E Date (m/d/yyyy), F Notes,
G Feelings (user-owned, never written). Per-tab budget cells H9/I9 (Weekly Budget) and
H10/I10 (Total Left + live formula). Dedup key = `teller-id:<id>` note on col A.

## Dedup rules (ported)

Match by col A `teller-id` note first; recover by content `(description, amount, date)`
when a note is missing; a manually-zeroed Cost row is left at $0 and not restored.

## Error handling

- Unparseable date range → clear message, no network calls.
- Teller per-account failure → collect + report, continue other accounts.
- Webhook non-200 or `{ok:false}` → fail that week's sync, retry once, report; do not mark
  partial success.

## Testing

- `daterange.py`: unit tests for every accepted form + error cases.
- Categorizer: port the Mini's existing tests.
- Sheet client: unit-test payload construction against a fake webhook; dedup logic tested
  against fixture `read` responses.
- End-to-end dry run against fixtures (no live Teller, no live sheet).

## Security

Code is public. Secrets (`~/.bank-mcp/*`, webhook URL+secret in `~/.config/daily-budget/`)
and personal data (real merchant map, state, budget figures) stay out of the repo per the
existing `.gitignore`.

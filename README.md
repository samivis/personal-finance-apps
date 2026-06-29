# personal-finance-apps

A small, dependency-free toolkit that asks for a date range, pulls bank transactions
from [Teller](https://teller.io), and syncs them into **Sun–Sat weekly tabs** of a
Google Sheet — without a fragile OAuth token that expires every 7 days.

> This is the open-source **engine**. All personal data (real transactions, merchant
> names, budget figures, bank credentials) lives outside this repo and is never
> committed — see [Security](#security).

---

## What it does

```
python3 budget_sync.py "last week"
```

1. Parses a flexible date-range string (`last week`, `yesterday to today`, `6/1 to 6/15`).
2. Fetches transactions from every linked Teller account over mutual-TLS.
3. Groups transactions by Sun–Sat week and identifies the correct Google Sheet tab for each week.
4. Deduplicates using `teller-id` stored in Google Sheets cell notes — reruns are safe.
5. Writes new rows and updates changed amounts; prints a per-tab summary.

---

## Architecture

```
budget_sync.py  (entry point)
      │
      ▼
personal_finance/           ← stdlib-only Python package
  orchestrator.py           ← parse range → fetch → group by week → sync each tab
  teller.py                 ← mutual-TLS calls to Teller API
  daterange.py              ← flexible natural-language date parser
  weeks.py                  ← Sun–Sat window logic + cascading rollover formula
  sync.py                   ← dedup + write via webhook
  sheet_client.py           ← HTTP client for the Apps Script webhook
  categorize.py             ← vendor → category rules (loaded from private data dir)

apps_script_webhook.gs      ← Google Apps Script deployed inside the Sheet
```

### Why Apps Script instead of the Sheets API directly

Google OAuth *Testing* apps issue refresh tokens that expire after exactly **7 days**.
The Apps Script approach runs the webhook **as the sheet owner** using a shared secret —
nothing expires, deploy once and forget it.

### Cascading rollover

Each week's **Weekly Budget** cell is a live Google Sheets formula:

```
=MAX(0, 'Monthly Budget'!C20 + prevWeek!I10)
```

Unspent money from the previous week rolls forward automatically. Overspending is
floored at zero (debt doesn't compound).

---

## Running

```bash
python3 budget_sync.py "last week"
python3 budget_sync.py "yesterday to today"
python3 budget_sync.py "6/1 to 6/15"
```

The script prompts for a date range if none is given on the command line.

### Prerequisites

| What | Where |
|------|--------|
| Teller mTLS cert + key | `~/.bank-mcp/keys/teller/certificate.pem` and `private_key.pem` |
| Teller config (enrollment/account IDs) | `~/.bank-mcp/config.json` |
| Webhook URL + secret | `~/.config/daily-budget/webhook.json` → `{"url": "...", "secret": "..."}` |
| Vendor rules (optional) | `../context/personal/data/finance/vendor-rules.json` |

### Webhook setup

1. Open your Google Sheet → Extensions → Apps Script.
2. Paste `apps_script_webhook.gs`, set `SHARED_SECRET` to a long random string.
3. Deploy as Web App (*Execute as: Me*, *Who has access: Anyone*).
4. Save the `/exec` URL and your secret to `~/.config/daily-budget/webhook.json`.

---

## Tests

```bash
python3 -m pytest tests/ -q
```

The test suite covers date parsing, week windowing, dedup logic, sheet client, and
the orchestrator — all with no network calls (Teller and Sheets are fully mocked).

---

## Repository layout

```
budget_sync.py              ← CLI entry point
personal_finance/           ← Python package (stdlib only)
apps_script_webhook.gs      ← Apps Script for the sheet webhook
tests/                      ← pytest suite
examples/                   ← sample merchant-categories and budget-spec formats
docs/superpowers/           ← spec and implementation plan (preserved for reference)
```

---

## Security

Code is public; **all secrets and personal data are git-ignored and never committed**:

- mTLS keys / certs (`*.pem`, `*.key`)
- Webhook URL and secret (`webhook.json`)
- Teller config, enrollment IDs, and access tokens (`config.json`)
- Real merchant map, run state, and budget figures (kept in a separate private repo)
- Bank statements and generated reports

`apps_script_webhook.gs` ships with the placeholder `CHANGE_ME_TO_A_LONG_RANDOM_STRING`;
the real secret exists only in your deployed Apps Script and your local `~/.config`.

---

## License

MIT

# personal-finance-apps

A small, dependency-free toolkit for automating a personal budget: pull bank
transactions, categorize them, and sync them to a Google Sheet — without a fragile
OAuth integration that breaks every week.

> This is the open-source **engine**. All personal data (real transactions, merchant
> names, budget figures, bank credentials) lives outside this repo and is never
> committed — see [Security model](#security-model).

## Why this exists

Most "connect your bank to a spreadsheet" setups rely on a Google OAuth app. Apps left
in Google's *Testing* publishing status hand out refresh tokens that expire after
exactly **7 days**, so the sync silently dies every week. This project sidesteps that
entirely:

- **Bank data** comes from [Teller](https://teller.io) over mutual-TLS, called directly
  (no broker), so a disconnected enrollment is detected and flagged instead of crashing
  the run.
- **Sheet writes** go through a Google **Apps Script Web App** that lives inside the
  sheet and runs as the owner — authenticated by a shared secret, not an OAuth token.
  Nothing expires. Deploy once.

## Architecture

```
Teller API (mTLS)  ─┐
                    ├─►  daily_budget_update.py  ─►  Apps Script webhook  ─►  Google Sheet
merchant map (JSON)─┘        │  fetch → dedupe → categorize → append → persist state
                            └─►  learns categories back from your sheet edits
```

### `daily_budget_update.py`
A single standalone script (Python stdlib only) that:
1. Loads run state (which transactions it has already recorded).
2. Fetches recent transactions from every linked Teller account over mTLS.
3. Deduplicates by transaction id and a date+merchant+amount+account fingerprint.
4. Categorizes each transaction from a merchant map; flags business expenses on
   personal cards.
5. Appends new rows to the sheet via the webhook.
6. Marks transactions "seen" **only** after a successful write (never on a dry run).
7. **Auto-learns**: reads categories you corrected in the sheet and folds them back into
   the merchant map, so each merchant is only ever categorized by hand once.

```bash
python3 daily_budget_update.py            # live run
python3 daily_budget_update.py --dry-run  # build rows, write a CSV, never touch the sheet
python3 daily_budget_update.py --hours 168  # widen the lookback window
```

### `apps_script_webhook.gs`
Paste into the sheet's Apps Script editor (Extensions → Apps Script), set a long random
`SHARED_SECRET`, and deploy as a Web App (*Execute as: Me*, *Who has access: Anyone*).
Supports `doPost` (append rows) and `doGet?action=read` (read rows back for auto-learn).

## Setup

1. **Teller**: create a Teller app, download your mTLS cert/key, and store them with your
   connection config (this toolkit reads them from `~/.bank-mcp/`).
2. **Webhook**: deploy `apps_script_webhook.gs`, then save your `/exec` URL + secret to
   `~/.config/daily-budget/webhook.json` as `{"url": "...", "secret": "..."}`.
3. Point the runner at your spreadsheet id + tab gid via its state file.

See [`examples/`](./examples) for the shape of the merchant map and the budget spec.

## Security model

Code is public; data is not. The following are **git-ignored and never committed**:

- mTLS keys/certs (`*.pem`), Teller config, the webhook secret/URL
- Your real merchant map and run state (these live in a separate private repo)
- The real budget spec, bank statements, and generated reports

The webhook script ships with a placeholder secret; the real value exists only in your
deployed Google Apps Script and your local `~/.config`.

## License

MIT

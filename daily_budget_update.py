#!/usr/bin/env python3
"""
Daily budget updater — local runner for this device.

Pipeline (mirrors context/personal/.claude/skills/daily-budget-update/SKILL.md):
  1. Load state
  2. Fetch last 24h of transactions from Teller (mTLS, straight to api.teller.io)
  3. Normalize + dedupe against state
  4. Categorize via merchant-categories.json
  5. Append new rows to the Google Sheet (Sheets API)  -- or dry-run if no creds
  6. Update state ONLY after a successful append
  7. Print a concise summary

Design rules baked in:
  - Teller is the only transaction source. If it fails, stop with the exact error.
    No invented fallback.
  - If Google Sheets write access is missing, DO NOT pretend. Write a dry-run
    payload to outputs/finance/ and exit cleanly without marking anything seen.
  - Nothing is marked "seen" unless the sheet append actually succeeded.

Run:
  python3 daily_budget_update.py             # live (needs Teller + Sheets creds)
  python3 daily_budget_update.py --dry-run   # force dry-run, skip the sheet write
  python3 daily_budget_update.py --hours 48  # widen the lookback window
"""

from __future__ import annotations

import argparse
import base64
import csv
import datetime as dt
import json
import os
import re
import ssl
import sys
import urllib.request
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
HOME = Path.home()
PROJECTS = Path(__file__).resolve().parent.parent          # .../Desktop/projects
PERSONAL = PROJECTS / "context" / "personal"
FINANCE_DIR = PERSONAL / "data" / "finance"

STATE_FILE = FINANCE_DIR / "daily-budget-state.json"
MERCHANTS_FILE = FINANCE_DIR / "merchant-categories.json"
OUTPUTS_DIR = PERSONAL / "outputs" / "finance"

BANK_MCP_CONFIG = HOME / ".bank-mcp" / "config.json"
TELLER_CERT = HOME / ".bank-mcp" / "keys" / "teller" / "certificate.pem"
TELLER_KEY = HOME / ".bank-mcp" / "keys" / "teller" / "private_key.pem"

# Google Sheets via Apps Script webhook (no OAuth app, nothing to disconnect).
# Set these once after deploying apps_script_webhook.gs as a Web app.
WEBHOOK_CONFIG = Path(os.environ.get(
    "DAILY_BUDGET_WEBHOOK_CONFIG",
    str(HOME / ".config" / "daily-budget" / "webhook.json")))

FALLBACK_CATEGORIES = {
    "Groceries", "Eating Out", "Shopping", "Health & Wellness",
    "Transportation", "Business", "Other", "Fixed",
}

SHEET_COLUMNS = ["Date", "Merchant", "Amount", "Category", "Account",
                 "Fixed", "Notes", "Source ID", "Ingested At"]


class BudgetError(Exception):
    """Clean, user-facing failure with remediation."""


# Connections skipped this run due to disconnected/MFA-required Teller enrollments.
DISCONNECTED_CONNECTIONS: list[str] = []


# ---------------------------------------------------------------------------
# Step 1: state
# ---------------------------------------------------------------------------
def load_state() -> dict:
    if not STATE_FILE.exists():
        return {
            "last_run_at": None,
            "last_successful_sheet_append_at": None,
            "last_error": None,
            "seen_transaction_ids": [],
            "seen_transaction_fingerprints": [],
            "unresolved_merchants": [],
            "flags": [],
            "sheet": {"spreadsheet_id": None, "gid": None},
        }
    return json.loads(STATE_FILE.read_text())


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2) + "\n")


# ---------------------------------------------------------------------------
# Step 2: fetch from Teller (mTLS, direct — bypasses bank-mcp's broken verify)
# ---------------------------------------------------------------------------
def _teller_get(path: str, access_token: str, ctx: ssl.SSLContext) -> list | dict:
    url = f"https://api.teller.io{path}"
    auth = base64.b64encode(f"{access_token}:".encode()).decode()
    req = urllib.request.Request(url, headers={"Authorization": f"Basic {auth}"})
    with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
        return json.loads(resp.read().decode())


def fetch_transactions(hours: int) -> list[dict]:
    """Pull recent transactions across every linked Teller account."""
    if not BANK_MCP_CONFIG.exists():
        raise BudgetError(
            f"Teller config not found at {BANK_MCP_CONFIG}.\n"
            "This device has no bank-mcp setup. To go live, copy the config + certs "
            "from the Mac Mini:\n"
            "  scp -r <macmini>:~/.bank-mcp ~/.bank-mcp\n"
            "(needs config.json + keys/teller/certificate.pem + private_key.pem)\n"
            "See personal-finance-apps/BANK_MCP_SETUP_SUMMARY.md."
        )
    if not (TELLER_CERT.exists() and TELLER_KEY.exists()):
        raise BudgetError(
            f"Teller mTLS cert/key missing ({TELLER_CERT}, {TELLER_KEY}). "
            "Copy keys/teller/*.pem from the Mac Mini."
        )

    ctx = ssl.create_default_context()
    ctx.load_cert_chain(certfile=str(TELLER_CERT), keyfile=str(TELLER_KEY))

    config = json.loads(BANK_MCP_CONFIG.read_text())
    connections = config.get("connections", [])
    if not connections:
        raise BudgetError(f"No Teller connections in {BANK_MCP_CONFIG}.")

    cutoff = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=hours)).date()
    out: list[dict] = []

    for conn in connections:
        cfg = conn.get("config", {})
        token = (conn.get("accessToken") or conn.get("access_token")
                 or cfg.get("accessToken") or cfg.get("access_token"))
        label = conn.get("label") or conn.get("id") or "unknown"
        if not token:
            raise BudgetError(f"Connection '{label}' has no access token in config.")

        try:
            accounts = _teller_get("/accounts", token, ctx)
        except urllib.error.HTTPError as e:
            # A disconnected/MFA-required enrollment (404) shouldn't kill the run.
            # Skip this connection, record a flag, keep going with the others.
            try:
                body = json.loads(e.read().decode())
                detail = body.get("error", {}).get("message", str(e))
            except Exception:
                detail = str(e)
            DISCONNECTED_CONNECTIONS.append(f"{label}: {detail}")
            continue
        for acct in accounts:
            if acct.get("status") not in (None, "open"):
                continue
            acct_id = acct["id"]
            acct_name = acct.get("name") or acct.get("last_four") or acct_id
            txns = _teller_get(f"/accounts/{acct_id}/transactions", token, ctx)
            for t in txns:
                tdate = t.get("date")
                if not tdate or dt.date.fromisoformat(tdate) < cutoff:
                    continue
                out.append({
                    "raw": t,
                    "account": acct_name,
                    "date": tdate,
                    "merchant": (t.get("description") or "").strip(),
                    "amount": t.get("amount") or t.get("amount_dec"),
                    "status": t.get("status"),
                    "source_id": t.get("id"),
                })
    # Prefer posted over pending; posted first.
    out.sort(key=lambda r: (r["status"] != "posted", r["date"]))
    return out


# ---------------------------------------------------------------------------
# Step 3: normalize + dedupe
# ---------------------------------------------------------------------------
def fingerprint(date: str, merchant: str, amount, account: str) -> str:
    norm = re.sub(r"\s+", " ", f"{date}|{merchant}|{amount}|{account}".lower()).strip()
    return norm


def dedupe(txns: list[dict], state: dict) -> tuple[list[dict], int]:
    seen_ids = set(state.get("seen_transaction_ids", []))
    seen_fps = set(state.get("seen_transaction_fingerprints", []))
    new, skipped = [], 0
    batch_fps = set()
    for t in txns:
        sid = t.get("source_id")
        fp = fingerprint(t["date"], t["merchant"], t["amount"], t["account"])
        if (sid and sid in seen_ids) or fp in seen_fps or fp in batch_fps:
            skipped += 1
            continue
        t["fingerprint"] = fp
        batch_fps.add(fp)
        new.append(t)
    return new, skipped


# ---------------------------------------------------------------------------
# Step 4: categorize
# ---------------------------------------------------------------------------
def load_merchant_map() -> dict:
    data = json.loads(MERCHANTS_FILE.read_text())
    return data.get("mappings", {}), data.get("red_flags", [])


def match_merchant(merchant: str, mappings: dict) -> dict | None:
    """Exact match first, then case-insensitive substring match. Returns the
    mapping entry or None. Shared by categorize() and the sheet learner."""
    hit = mappings.get(merchant)
    if not hit:
        ml = merchant.lower()
        for name, m in mappings.items():
            if name.lower() in ml:
                return m
    return hit


def categorize(txns: list[dict], mappings: dict, red_flags: list, state: dict) -> None:
    for t in txns:
        merchant = t["merchant"]
        cat, fixed, note = "Other", False, ""
        hit = match_merchant(merchant, mappings)
        if hit:
            cat = hit.get("category", "Other")
            fixed = bool(hit.get("fixed", False))
            note = hit.get("note", "")
        else:
            if merchant:
                state.setdefault("unresolved_merchants", [])
                if merchant not in state["unresolved_merchants"]:
                    state["unresolved_merchants"].append(merchant)
            note = "unmapped merchant — review category"

        flags = []
        if cat == "Business":
            flags.append("BUSINESS expense on personal card — move to biz card")
        for rf in red_flags:
            if rf.get("pattern", "").lower() in merchant.lower():
                flags.append(f"RED FLAG: {rf.get('reason', rf['pattern'])}")
        if flags:
            t["flags"] = flags
            state.setdefault("flags", [])
            for f in flags:
                state["flags"].append({"merchant": merchant, "date": t["date"], "flag": f})

        t["category"] = cat
        t["fixed"] = fixed
        t["notes"] = note


# ---------------------------------------------------------------------------
# Step 5: append to Google Sheet (or dry-run)
# ---------------------------------------------------------------------------
def to_row(t: dict, ingested_at: str) -> list:
    return [
        t["date"], t["merchant"], str(t["amount"]), t["category"],
        t["account"], "TRUE" if t["fixed"] else "FALSE",
        t.get("notes", ""), t.get("source_id", ""), ingested_at,
    ]


def append_to_sheet(rows: list[list], spreadsheet_id: str, gid) -> bool:
    """Append rows to the sheet via the Apps Script webhook. Returns True on success.

    Raises BudgetError if the webhook isn't configured so the caller can dry-run.
    The webhook lives inside the sheet (Apps Script) — no OAuth app, nothing that
    can disconnect. Configure once in WEBHOOK_CONFIG: {"url": "...", "secret": "..."}.
    """
    if not WEBHOOK_CONFIG.exists():
        raise BudgetError(
            f"Sheet webhook not configured at {WEBHOOK_CONFIG}.\n"
            "Deploy personal-finance-apps/apps_script_webhook.gs as a Web app, then save:\n"
            '  {"url": "https://script.google.com/.../exec", "secret": "<same as script>"}\n'
            f"  to {WEBHOOK_CONFIG}"
        )
    cfg = json.loads(WEBHOOK_CONFIG.read_text())
    url, secret = cfg.get("url"), cfg.get("secret")
    if not url or not secret:
        raise BudgetError(f"{WEBHOOK_CONFIG} must contain both 'url' and 'secret'.")

    payload = json.dumps({"secret": secret, "rows": rows}).encode()
    req = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read().decode())
    if not result.get("ok"):
        raise BudgetError(f"Webhook rejected the write: {result.get('error')}")
    return True


# ---------------------------------------------------------------------------
# Auto-learn: read user-corrected categories back from the sheet and remember
# them, so a merchant only ever needs to be categorized by hand once.
# ---------------------------------------------------------------------------
def fetch_sheet_rows() -> list[list]:
    """GET all rows from the sheet via the webhook's read action.

    Returns [] (silently) if the webhook isn't configured or doesn't support
    reading yet — learning is best-effort and must never block the main run.
    """
    if not WEBHOOK_CONFIG.exists():
        return []
    cfg = json.loads(WEBHOOK_CONFIG.read_text())
    url, secret = cfg.get("url"), cfg.get("secret")
    if not url or not secret:
        return []
    import urllib.parse
    q = urllib.parse.urlencode({"secret": secret, "action": "read"})
    try:
        with urllib.request.urlopen(f"{url}?{q}", timeout=30) as resp:
            data = json.loads(resp.read().decode())
    except Exception:
        return []
    return data.get("rows", []) if data.get("ok") else []


def learn_from_sheet(state: dict) -> int:
    """Read the sheet and learn any user-assigned category for a merchant we
    didn't already resolve to that same category. Returns count learned."""
    rows = fetch_sheet_rows()
    if not rows:
        return 0
    full = json.loads(MERCHANTS_FILE.read_text())
    mappings = full.setdefault("mappings", {})
    header = rows[0]
    try:
        mi, ci, fi = (header.index("Merchant"), header.index("Category"),
                      header.index("Fixed"))
    except ValueError:
        mi, ci, fi = 1, 3, 5  # default column order
    learned = 0
    for r in rows[1:]:
        if len(r) <= max(mi, ci):
            continue
        merchant = (str(r[mi]) if r[mi] is not None else "").strip()
        cat = (str(r[ci]) if r[ci] is not None else "").strip()
        if not merchant or cat not in FALLBACK_CATEGORIES or cat == "Other":
            continue
        # Skip if we already resolve this merchant to the same category.
        existing = match_merchant(merchant, mappings)
        if existing and existing.get("category") == cat:
            continue
        fixed = len(r) > fi and str(r[fi]).strip().upper() == "TRUE"
        mappings[merchant] = {"category": cat, "fixed": fixed,
                              "note": "learned from sheet correction"}
        learned += 1
        # Once learned, it's no longer unresolved.
        if merchant in state.get("unresolved_merchants", []):
            state["unresolved_merchants"].remove(merchant)
    if learned:
        full["last_updated"] = dt.date.today().isoformat()
        MERCHANTS_FILE.write_text(json.dumps(full, indent=2) + "\n")
    return learned


def write_dry_run(rows: list[list], reason: str) -> Path:
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    path = OUTPUTS_DIR / f"daily-budget-dryrun-{stamp}.csv"
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(SHEET_COLUMNS)
        w.writerows(rows)
    (OUTPUTS_DIR / f"daily-budget-dryrun-{stamp}.json").write_text(
        json.dumps({"reason": reason, "row_count": len(rows),
                    "columns": SHEET_COLUMNS, "rows": rows}, indent=2) + "\n"
    )
    return path


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description="Daily budget updater (local runner)")
    ap.add_argument("--hours", type=int, default=24, help="lookback window in hours")
    ap.add_argument("--dry-run", action="store_true", help="never write to the sheet")
    args = ap.parse_args()

    state = load_state()
    now_iso = dt.datetime.now(dt.timezone.utc).isoformat()
    state["last_run_at"] = now_iso

    try:
        txns = fetch_transactions(args.hours)
    except BudgetError as e:
        state["last_error"] = str(e)
        save_state(state)
        print(f"FETCH FAILED — stopping (no fallback source):\n{e}", file=sys.stderr)
        return 2

    new, skipped = dedupe(txns, state)
    # Learn from any categories I corrected in the sheet since last run, THEN
    # load the (now-updated) map so this run benefits immediately.
    learned = learn_from_sheet(state)
    mappings, red_flags = load_merchant_map()
    categorize(new, mappings, red_flags, state)

    ingested_at = now_iso
    rows = [to_row(t, ingested_at) for t in new]

    total = 0.0
    for t in new:
        try:
            total += float(t["amount"])
        except (TypeError, ValueError):
            pass

    flags = [f for t in new for f in t.get("flags", [])]

    sheet_cfg = state.get("sheet", {})
    spreadsheet_id = sheet_cfg.get("spreadsheet_id")
    gid = sheet_cfg.get("gid")

    sheet_written = False
    dry_reason = None
    if not rows:
        print("No new transactions in the window — nothing to append.")
    elif args.dry_run:
        dry_reason = "forced --dry-run"
    else:
        try:
            sheet_written = append_to_sheet(rows, spreadsheet_id, gid)
        except BudgetError as e:
            dry_reason = str(e)

    if rows and sheet_written:
        # Step 6: mark seen ONLY after a real append.
        ids = state.setdefault("seen_transaction_ids", [])
        fps = state.setdefault("seen_transaction_fingerprints", [])
        for t in new:
            if t.get("source_id"):
                ids.append(t["source_id"])
            fps.append(t["fingerprint"])
        state["last_successful_sheet_append_at"] = now_iso
        state["last_error"] = None
        save_state(state)
    elif rows:
        path = write_dry_run(rows, dry_reason or "dry-run")
        state["last_error"] = f"dry-run: {dry_reason}"
        save_state(state)  # note: seen lists intentionally NOT updated
        print(f"DRY-RUN — sheet NOT written. Rows saved to: {path}\nReason: {dry_reason}")
    else:
        save_state(state)

    # Step 7: summary
    print("\n=== Daily Budget Update ===")
    print(f"Fetched:     {len(txns)} txns (last {args.hours}h)")
    print(f"New:         {len(new)}")
    print(f"Duplicates:  {skipped}")
    print(f"Window spend: {total:.2f}")
    print(f"Sheet:       {'APPENDED' if sheet_written else 'DRY-RUN / not written'}")
    if learned:
        print(f"Learned:     {learned} merchant categories from sheet corrections")
    if flags:
        print("Flags:")
        for f in flags:
            print(f"  - {f}")
    if state.get("unresolved_merchants"):
        print(f"Unresolved merchants: {', '.join(state['unresolved_merchants'][-10:])}")
    if DISCONNECTED_CONNECTIONS:
        print("Disconnected connections (re-auth needed in Teller Connect):")
        for d in DISCONNECTED_CONNECTIONS:
            print(f"  - {d}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

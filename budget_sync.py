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

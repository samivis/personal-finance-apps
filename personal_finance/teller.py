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

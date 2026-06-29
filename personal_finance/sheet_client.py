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

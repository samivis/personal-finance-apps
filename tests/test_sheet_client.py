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

def test_delete_rows():
    post = FakePost({"delete_rows": {"ok": True, "deleted": 3}})
    c = SheetClient("u", "s", http_post=post)
    assert c.delete_rows("6/1-6/7", 5, 3) == 3
    assert post.calls[0] == {"action": "delete_rows", "tab": "6/1-6/7", "start_row": 5, "num_rows": 3, "secret": "s"}

def test_raises_on_not_ok():
    post = FakePost({"list_tabs": {"ok": False, "error": "bad secret"}})
    c = SheetClient("u", "s", http_post=post)
    try:
        c.list_tabs(); assert False
    except RuntimeError as e:
        assert "bad secret" in str(e)

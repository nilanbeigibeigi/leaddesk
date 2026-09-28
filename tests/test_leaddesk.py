"""Tests with FastAPI's TestClient and a fake AI (no Ollama needed)."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("LEADDESK_DB", str(tmp_path / "t.db"))
    import importlib, app.db, app.ai, app.main
    importlib.reload(app.db); importlib.reload(app.ai); importlib.reload(app.main)
    with TestClient(app.main.app) as c:
        yield c


def test_pages_load(client):
    for url in ["/", "/pipeline", "/contacts", "/deals/1"]:
        assert client.get(url).status_code == 200, url
    assert client.get("/deals/999").status_code == 404


def test_follow_ups_show_overdue_and_quiet(client):
    html = client.get("/").text
    assert "Rose Hair Studio" in html and "days overdue" in html   # overdue next step
    assert "days quiet" in html                                     # no contact in 14+ days


def test_move_stage_updates_board_and_history(client):
    r = client.post("/deals/2/move", data={"stage": "Won"})
    assert r.status_code == 200 and 'id="board"' in r.text
    assert "Moved to Won" in client.get("/deals/2").text
    assert client.post("/deals/2/move", data={"stage": "Maybe"}).status_code == 400


def test_add_lead_creates_contact_and_deal(client):
    r = client.post("/contacts", data={"name": "Test Person", "company": "Test Co (sample)", "title": "Website",
                                       "service": "Website", "value": 900}, follow_redirects=True)
    assert "Test Co (sample)" in r.text and "Website" in r.text


def test_activity_is_added(client):
    r = client.post("/deals/1/activities", data={"kind": "Call", "note": "She approved the quote"})
    assert "She approved the quote" in r.text


def test_ai_draft_and_fallback(client, monkeypatch):
    from app import ai
    monkeypatch.setattr(ai, "_chat", lambda s, u: json.dumps({"subject": "Your café menu site", "body": "Hi Leila, ..."}))
    r = client.post("/deals/1/draft", data={"language": "English"})
    assert "Your café menu site" in r.text and "mailto:leila@example.com" in r.text
    def broken(s, u): raise ConnectionError("off")
    monkeypatch.setattr(ai, "_chat", broken)
    r = client.post("/deals/1/draft", data={"language": "Farsi"})
    assert "standard template" in r.text and "سلام" in r.text


def test_can_start_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("LEADDESK_DB", str(tmp_path / "e.db")); monkeypatch.setenv("LEADDESK_SEED", "0")
    import importlib, app.db
    importlib.reload(app.db); app.db.init()
    assert app.db.one("SELECT COUNT(*) AS n FROM contacts")["n"] == 0

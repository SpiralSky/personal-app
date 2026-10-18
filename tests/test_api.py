from fastapi.testclient import TestClient

from campus_assistant.api import create_app
from campus_assistant.config import Config
from campus_assistant.store import Store


def client(tmp_path):
    cfg = Config(data_dir=tmp_path)
    cfg.ensure_dirs()
    return TestClient(create_app(cfg, Store(cfg.db_path), schedule=False, analyze=False))


EMAIL = {
    "source": "outlook", "kind": "email", "external_id": "AAMkAD123",
    "title": "Internship fair next week", "body": "Register by Friday",
    "occurred_at": "2026-10-07T09:00:00Z", "data": {"from": "careers@sp.edu.sg", "folder": "Inbox"},
}


def test_ingest_and_read(tmp_path):
    c = client(tmp_path)
    r = c.post("/ingest", json={"items": [EMAIL]})
    assert r.json() == {"received": 1, "created": 1}
    r = c.post("/ingest", json={"items": [EMAIL]})
    assert r.json() == {"received": 1, "unchanged": 1}

    rows = c.get("/items", params={"source": "outlook"}).json()
    assert rows[0]["id"] == "outlook:email:AAMkAD123"
    one = c.get("/items/outlook:email:AAMkAD123").json()
    assert one["data"]["from"] == "careers@sp.edu.sg" and one["file"] is None
    assert c.get("/items/nope").status_code == 404


def test_upcoming_and_ics(tmp_path):
    c = client(tmp_path)
    task = {"source": "brightspace:splms", "kind": "assignment", "external_id": "1:1",
            "title": "Assignment 1, part A", "course_name": "ST1522", "due_at": "2099-01-01T10:00:00Z"}
    c.post("/ingest", json={"items": [task]})
    assert c.get("/upcoming", params={"days": 100000}).json()[0]["title"] == "Assignment 1, part A"

    ics = c.get("/calendar.ics")
    assert ics.headers["content-type"].startswith("text/calendar")
    body = ics.text
    assert "DTSTART:20990101T100000Z" not in body  # outside the 365-day window
    c.post("/ingest", json={"items": [{**task, "external_id": "1:2", "due_at": "2026-12-01T10:00:00Z"}]})
    body = c.get("/calendar.ics").text
    assert "DTSTART:20261201T100000Z" in body and "SUMMARY:Assignment 1\\, part A (ST1522)" in body
    assert all(len(line.encode()) <= 75 for line in body.split("\r\n"))


def test_web_ui_served(tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>app</html>")
    (dist / "assets" / "x.js").write_text("console.log(1)")
    (dist / "favicon.svg").write_text("<svg/>")
    cfg = Config(data_dir=tmp_path / "data", web_dist=dist)
    cfg.ensure_dirs()
    c = TestClient(create_app(cfg, Store(cfg.db_path), schedule=False, analyze=False))
    assert c.get("/", follow_redirects=False).headers["location"] == "/ui/"
    assert c.get("/ui/").text == "<html>app</html>"
    assert c.get("/ui/inbox").text == "<html>app</html>"
    assert c.get("/ui/assets/x.js").text == "console.log(1)"
    assert c.get("/ui/favicon.svg").text == "<svg/>"
    assert c.get("/ui/..%2Fdata%2Fcampus.db").text == "<html>app</html>"
    assert c.get("/health").json() == {"ok": True}


def test_web_ui_absent(tmp_path):
    cfg = Config(data_dir=tmp_path, web_dist=tmp_path / "missing")
    cfg.ensure_dirs()
    c = TestClient(create_app(cfg, Store(cfg.db_path), schedule=False, analyze=False))
    assert c.get("/ui/").status_code == 404

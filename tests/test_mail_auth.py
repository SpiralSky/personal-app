import asyncio
import base64
import json

from fastapi.testclient import TestClient

from campus_assistant import runner as runner_mod
from campus_assistant.api import create_app
from campus_assistant.brightspace.sync import SyncReport
from campus_assistant.config import Config
from campus_assistant.mail import EmailIn, email_item, iter_archive, short_hash
from campus_assistant.runner import BrightspaceRunner
from campus_assistant.store import Store

EML = (
    b"From: Careers Centre <careers@sp.edu.sg>\r\n"
    b"To: Student <sans.25@ichat.sp.edu.sg>\r\n"
    b"Subject: Internship fair on 20 Oct\r\n"
    b"Date: Tue, 06 Oct 2026 09:30:00 +0800\r\n"
    b"Message-ID: <abc@sp.edu.sg>\r\n"
    b"List-Unsubscribe: <mailto:unsub@sp.edu.sg>\r\n"
    b"MIME-Version: 1.0\r\n"
    b"Content-Type: multipart/mixed; boundary=XX\r\n\r\n"
    b"--XX\r\nContent-Type: text/html; charset=utf-8\r\n\r\n<p>Register <b>by Friday</b></p>\r\n"
    b"--XX\r\nContent-Type: application/pdf\r\nContent-Disposition: attachment; filename=\"flyer.pdf\"\r\n"
    b"Content-Transfer-Encoding: base64\r\n\r\nJVBERi0=\r\n--XX--\r\n"
)


def test_email_item_from_mime():
    it = email_item(EmailIn(item_id="AAMk==", folder="Inbox", mime_base64=base64.b64encode(EML).decode()))
    assert it.id == f"outlook:email:{short_hash('AAMk==')}"
    assert it.title == "Internship fair on 20 Oct"
    assert it.body == "Register by Friday"
    assert it.occurred_at == "2026-10-06T01:30:00Z"
    assert it.data["from"] == "Careers Centre <careers@sp.edu.sg>"
    assert it.data["bulk"] is True and it.data["has_mime"] is True
    assert it.data["attachments"][0]["name"] == "flyer.pdf"


def test_short_hash_matches_fork():
    # node -e 'require("crypto").createHash("sha1").update("AAMk==").digest("hex").slice(0,16)'
    import hashlib
    assert short_hash("AAMk==") == hashlib.sha1(b"AAMk==").hexdigest()[:16]


def test_iter_archive(tmp_path):
    acct = tmp_path / "me@sp.edu.sg"
    (acct / "Inbox").mkdir(parents=True)
    (acct / "Inbox" / "a.eml").write_bytes(EML)
    (acct / "Inbox" / "b.html").write_text("<p>Snapshot</p>")
    (acct / "Inbox" / "b.json").write_text(json.dumps({"Subject": "Hi", "From": {"Mailbox": {"EmailAddress": "x@y"}},
                                                       "DateTimeReceived": "2026-10-01T00:00:00Z"}))
    (acct / "index.json").write_text(json.dumps({"version": 1, "folders": {"f1": {"name": "Inbox"}}, "items": {
        "k1": {"files": ["Inbox/a.eml"], "mime": True, "folderId": "f1"},
        "k2": {"files": ["Inbox/b.html", "Inbox/b.json"], "mime": False, "folderId": "f1"},
    }}))
    items = {i.external_id: i for i in map(email_item, iter_archive(tmp_path))}
    assert items["k1"].title == "Internship fair on 20 Oct" and items["k1"].data["folder"] == "Inbox"
    assert items["k2"].body == "Snapshot" and items["k2"].data["from"] == "x@y" and not items["k2"].data["has_mime"]


def test_ingest_email_endpoint(tmp_path):
    cfg = Config(data_dir=tmp_path)
    cfg.ensure_dirs()
    c = TestClient(create_app(cfg, Store(cfg.db_path), schedule=False, analyze=False))
    r = c.post("/ingest/email", json={"messages": [
        {"item_id": "A1", "html": "<p>Hello</p>", "subject": "Hi", "sender": "a@b", "received_at": "2026-10-01T00:00:00Z"},
        {"folder": "Inbox"},  # no id → reported, not fatal
    ]}).json()
    assert r["received"] == 2 and r["created"] == 1 and r["errors"][0]["index"] == 1
    # Upgrade to MIME later: same item, now updated.
    r = c.post("/ingest/email", json={"messages": [{"item_id": "A1", "mime_base64": base64.b64encode(EML).decode()}]})
    assert r.json()["updated"] == 1


def test_auth_state_from_sync(tmp_path, monkeypatch):
    cfg = Config(data_dir=tmp_path, bs_hosts=["splms.x", "lms.x"])
    cfg.ensure_dirs()
    r = BrightspaceRunner(Store(cfg.db_path), cfg)
    assert r.auth()["state"] == "unknown"

    async def fake_sync(store, cfg, hosts=None):
        rep = SyncReport()
        rep.hosts["splms.x"] = {"user": "me"}
        rep.login_required.append("lms.x")
        return rep

    monkeypatch.setattr(runner_mod, "sync_brightspace", fake_sync)
    asyncio.run(r.sync())
    auth = r.auth()
    assert auth["state"] == "login_required"
    assert auth["hosts"]["splms.x"]["state"] == "ok" and auth["hosts"]["splms.x"]["user"] == "me"
    assert auth["hosts"]["lms.x"]["state"] == "login_required"
    assert r._hosts_needing_login() == ["lms.x"]

    # Persisted: a new runner (e.g. after restart) sees the same state.
    assert BrightspaceRunner(Store(cfg.db_path), cfg).auth()["state"] == "login_required"


def test_lone_surrogates_are_cleaned(tmp_path):
    from campus_assistant.models import ItemIn
    s = Store(tmp_path / "db.sqlite")
    it = ItemIn(source="outlook", kind="email", external_id="x", title="Hi \ud83d", body="a\x00b",
                data={"to": ["\udc00z"]})
    assert s.upsert(it) == "created"
    row = s.get(it.id)
    assert row["title"] == "Hi �" and row["body"] == "ab" and row["data"]["to"] == ["�z"]


def test_iter_archive_newest_copy_wins(tmp_path):
    import os
    for i, (acct, folder) in enumerate([("old", "Inbox"), ("new", "Archive")]):
        d = tmp_path / acct / folder
        d.mkdir(parents=True)
        (d / "a.eml").write_bytes(EML)
        idx = tmp_path / acct / "index.json"
        idx.write_text(json.dumps({"version": 1, "folders": {"f": {"name": folder}},
                                   "items": {"k": {"files": [f"{folder}/a.eml"], "mime": True, "folderId": "f"}}}))
        os.utime(idx, (1000 + i, 1000 + i))
    got = list(iter_archive(tmp_path))
    assert len(got) == 1 and got[0].folder == "Archive" and got[0].account == "new"

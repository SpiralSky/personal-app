import asyncio
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from campus_assistant.analysis.pipeline import Analyzer, rank_files
from campus_assistant.analysis.schemas import MessageTriage, TaskBrief
from campus_assistant.api import create_app
from campus_assistant.config import Config
from campus_assistant.llm import LLMError, Usage
from campus_assistant.models import ItemIn
from campus_assistant.store import Store

NOW = datetime.now(UTC)
iso = lambda dt: dt.strftime("%Y-%m-%dT%H:%M:%SZ")  # noqa: E731


class FakeLLM:
    name, model, max_input_chars = "fake", "fake-1", 5000

    def __init__(self, fail_on: str | None = None):
        self.calls: list[str] = []
        self.fail_on = fail_on

    async def structured(self, *, system, user, schema, effort="low", max_tokens=4000):
        self.calls.append(user)
        if self.fail_on and self.fail_on in user:
            raise LLMError("boom")
        if schema is MessageTriage:
            return MessageTriage(category="opportunity", priority="soon", summary="Fair.", actions=[], dates=[],
                                 opportunity=None, links=[]), Usage(10, 5)
        return TaskBrief(summary="Do it.", deliverables=["x"], requirements=[], submission=None, weightage=None,
                         relevant_files=[], plan=[], open_questions=[], confidence="low"), Usage(20, 8)


def email(eid, sender, subject="Hi", days_ago=1, body="Body"):
    return ItemIn(source="outlook", kind="email", external_id=eid, title=subject, body=body,
                  occurred_at=iso(NOW - timedelta(days=days_ago)), data={"from": sender})


def seeded(tmp_path):
    s = Store(tmp_path / "db.sqlite")
    s.set_meta("auth:brightspace", {"splms": {"state": "ok", "user": "me@ichat.sp.edu.sg"}})
    s.upsert_many([
        email("1", "Careers <careers@sp.edu.sg>", "Internship fair"),
        email("2", "System <email@splms.polite.edu.sg>", "New grade"),
        email("3", "Me <ME@ichat.sp.edu.sg>", "Re: project"),
        email("4", "old@sp.edu.sg", "Ancient", days_ago=400),
        ItemIn(source="brightspace:splms", kind="assignment", external_id="1:9", title="Assignment 1",
               course_id="1", course_name="ST1522", due_at=iso(NOW + timedelta(days=10)), data={"submitted": False}),
        ItemIn(source="brightspace:splms", kind="assignment", external_id="1:8", title="Done already",
               course_id="1", course_name="ST1522", due_at=iso(NOW + timedelta(days=5)), data={"submitted": True}),
    ])
    return s


def test_triage_rules_llm_and_caching(tmp_path):
    s = seeded(tmp_path)
    llm = FakeLLM()
    a = Analyzer(s, triage_provider=llm, brief_provider=llm, use_defaults=False)
    counts = asyncio.run(a.triage(since_days=30))
    assert counts == {"rules": 2, "fake": 1}  # LMS copy + own mail by rule; one LLM call; old mail skipped
    assert len(llm.calls) == 1 and "Internship fair" in llm.calls[0] and "Today:" in llm.calls[0]
    assert s.get_analysis("outlook:email:2", "triage")["result"]["category"] == "system"
    assert s.get_analysis("outlook:email:3", "triage")["result"]["summary"] == "Sent by you."

    # Unchanged input → nothing to do. Changed content → redone.
    assert asyncio.run(a.triage(since_days=30)) == {}
    s.upsert(email("1", "Careers <careers@sp.edu.sg>", "Internship fair", body="Updated body"))
    assert asyncio.run(a.triage(since_days=30)) == {"fake": 1}


def test_errors_are_stored_and_retried(tmp_path):
    s = seeded(tmp_path)
    a = Analyzer(s, triage_provider=FakeLLM(fail_on="Internship"), use_defaults=False)
    assert asyncio.run(a.triage(since_days=30))["errors"] == 1
    assert s.get_analysis("outlook:email:1", "triage")["error"] == "boom"
    a.triage_llm = FakeLLM()
    assert asyncio.run(a.triage(since_days=30)) == {"fake": 1}


def test_no_llm_configured(tmp_path):
    s = seeded(tmp_path)
    counts = asyncio.run(Analyzer(s, use_defaults=False).triage(since_days=30))
    assert counts == {"rules": 2, "skipped_no_llm": 1}


def test_briefs_skip_submitted(tmp_path):
    s = seeded(tmp_path)
    llm = FakeLLM()
    counts = asyncio.run(Analyzer(s, brief_provider=llm, use_defaults=False).briefs(horizon_days=30))
    assert counts == {"fake": 1}
    assert "Assignment 1" in llm.calls[0] and "Already submitted: no" in llm.calls[0]
    assert s.get_analysis("brightspace:splms:assignment:1:9", "brief")["result"]["confidence"] == "low"


def f(title, filename="", path=()):
    return {"title": title, "filename": filename, "data": {"module_path": list(path)}, "path": "", "sha256": ""}


def test_rank_files():
    files = [
        f("Week 3 notes", "notes3.pdf"),
        f("Assignment 2 Brief", "A2_brief.pdf"),
        f("CA1 Assignment1 specification", "ST1522_Assignment1_Spec.pdf"),
        f("Video", "intro.html", ["Learning", "MAI Assignment"]),
    ]
    ranked = rank_files("Assignment 1", files)
    assert [r["title"] for r in ranked][:1] == ["CA1 Assignment1 specification"]
    assert "Week 3 notes" not in [r["title"] for r in ranked]
    # Same module as a link to the task beats name matching.
    ranked = rank_files("MAI Assignment", files, anchor_paths=[["Learning", "MAI Assignment"]])
    assert ranked[0]["title"] == "Video"


def test_triage_and_label_api(tmp_path):
    cfg = Config(data_dir=tmp_path)
    cfg.ensure_dirs()
    s = seeded(tmp_path)
    asyncio.run(Analyzer(s, triage_provider=FakeLLM(), use_defaults=False).triage(since_days=30))
    c = TestClient(create_app(cfg, s, schedule=False, analyze=False))

    rows = c.get("/triage").json()
    assert [r["title"] for r in rows] == ["Internship fair"]  # "ignore" priority hidden by default
    assert len(c.get("/triage", params={"include_ignored": True}).json()) == 3
    assert c.get("/triage", params={"category": "opportunity"}).json()[0]["priority"] == "soon"

    r = c.post("/items/outlook:email:1/label", json={"category": "notice", "priority": "ignore"})
    assert r.status_code == 200
    assert c.get("/triage").json() == []
    row = c.get("/triage", params={"category": "notice", "include_ignored": True}).json()[0]
    assert row["corrected"] and row["triage"]["category"] == "opportunity"
    assert c.get("/items/outlook:email:1").json()["label"]["category"] == "notice"
    assert c.post("/items/nope/label", json={}).status_code == 404
    assert c.post("/items/outlook:email:1/label", json={"category": "bogus"}).status_code == 422


def test_tidy_urls():
    from campus_assistant.text import tidy_url, tidy_urls
    li = "https://www.linkedin.com/comm/jobs/view/4473219836/?trackingId=abc%3D&refId=x&lipi=urn%3Ali"
    assert tidy_url(li) == "https://www.linkedin.com/comm/jobs/view/4473219836/"
    safe = ("https://apc01.safelinks.protection.outlook.com/?url=https%3A%2F%2Fforms.office.com%2Fr%2FAbC123%3Fid%3D7"
            "&data=05%7C02%7Cx&reserved=0")
    assert tidy_url(safe) == "https://forms.office.com/r/AbC123?id=7"
    assert len(tidy_url("https://x.com/" + "a" * 500)) == 150
    assert tidy_urls(f"Apply: {li} now") == "Apply: https://www.linkedin.com/comm/jobs/view/4473219836/ now"

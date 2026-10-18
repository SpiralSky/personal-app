from campus_assistant.models import ItemIn
from campus_assistant.store import ANY_COURSE, Store


def make(**kw):
    base = dict(source="brightspace:splms", kind="assignment", external_id="1:10", title="Lab 2",
                course_id="1", course_name="ST1522", due_at="2026-10-30T10:00:00.000Z", data={"raw": {"x": 1}})
    return ItemIn(**{**base, **kw})


def test_dates_normalised_to_utc_z():
    assert make(due_at="2026-10-30T18:00:00+08:00").due_at == "2026-10-30T10:00:00Z"
    assert make(due_at=None).due_at is None


def test_create_unchanged_update(tmp_path):
    s = Store(tmp_path / "db.sqlite")
    assert s.upsert(make(), now="2026-10-01T00:00:00Z") == "created"
    # raw-only differences are not changes
    assert s.upsert(make(data={"raw": {"x": 2}}), now="2026-10-02T00:00:00Z") == "unchanged"
    assert s.get(make().id)["data"]["raw"] == {"x": 2}
    assert s.upsert(make(due_at="2026-11-06T10:00:00Z"), now="2026-10-03T00:00:00Z") == "updated"

    changes = s.changes()
    assert [c["change"] for c in changes] == ["updated", "created"]
    assert changes[0]["fields"] == ["due_at"]
    hist = s.history(make().id)
    assert len(hist) == 1 and hist[0]["snapshot"]["due_at"] == "2026-10-30T10:00:00Z"


def test_data_field_changes_are_named(tmp_path):
    s = Store(tmp_path / "db.sqlite")
    s.upsert(make())
    s.upsert(make(data={"submitted": True}))
    assert s.changes()[0]["fields"] == ["data.submitted"]


def test_mark_missing_and_restore(tmp_path):
    s = Store(tmp_path / "db.sqlite")
    a, b = make(), make(external_id="1:11", title="Lab 3")
    s.upsert_many([a, b])
    assert s.mark_missing("brightspace:splms", "assignment", "1", {a.id}) == 1
    assert s.get(b.id)["deleted_at"] is not None
    assert [i["id"] for i in s.query(kind="assignment")] == [a.id]
    assert s.upsert(b) == "restored"
    assert s.get(b.id)["deleted_at"] is None


def test_mark_missing_any_course(tmp_path):
    s = Store(tmp_path / "db.sqlite")
    c1 = make(kind="course", external_id="1", course_id="1")
    c2 = make(kind="course", external_id="2", course_id="2")
    s.upsert_many([c1, c2])
    assert s.mark_missing("brightspace:splms", "course", ANY_COURSE, {c1.id}) == 1


def test_upcoming_and_query_prefix(tmp_path):
    s = Store(tmp_path / "db.sqlite")
    s.upsert_many([
        make(),
        make(external_id="1:11", due_at="2027-03-01T00:00:00Z"),
        make(kind="announcement", external_id="1:5", due_at=None, occurred_at="2026-10-01T00:00:00Z"),
    ])
    due = s.upcoming("2026-10-08T00:00:00Z", "2026-11-08T00:00:00Z")
    assert [d["external_id"] for d in due] == ["1:10"]
    assert len(s.query(source="brightspace")) == 3
    assert len(s.query(source="outlook")) == 0


def test_meta_is_not_a_change(tmp_path):
    s = Store(tmp_path / "db.sqlite")
    s.upsert(make(data={"meta": {"path": "/old/a.eml"}}))
    assert s.upsert(make(data={"meta": {"path": "/new/a.eml"}})) == "unchanged"
    assert s.get(make().id)["data"]["meta"] == {"path": "/new/a.eml"}


def test_failed_analysis_keeps_previous_result(tmp_path):
    from campus_assistant.store import Store

    store = Store(tmp_path / "db.sqlite")
    store.save_analysis("x", "triage", "h1", "local", "qwen", {"category": "notice"})
    store.save_analysis("x", "triage", "h2", "local", "qwen", error="LLM unreachable")
    a = store.get_analysis("x", "triage")
    assert a["result"] == {"category": "notice"} and a["error"] == "LLM unreachable"  # kept, still retried
    store.save_analysis("x", "triage", "h2", "local", "qwen", {"category": "deadline"})
    a = store.get_analysis("x", "triage")
    assert a["result"] == {"category": "deadline"} and a["error"] is None
    store.save_analysis("y", "triage", "h1", "local", "qwen", error="boom")
    assert store.get_analysis("y", "triage")["result"] is None

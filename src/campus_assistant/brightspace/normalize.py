"""Brightspace (Valence API) JSON → ItemIn. Pure functions, no I/O.

Only fields that matter to the user go in `data` (they drive change
detection); the full API object goes in `data["raw"]`, which is not hashed,
so counters like TotalUsersWithSubmissions don't register as changes.
"""

from dataclasses import dataclass
from typing import Any

from ..models import ItemIn
from ..text import rich_text


@dataclass(frozen=True)
class Course:
    host: str
    id: str
    name: str
    code: str | None = None

    @property
    def source(self) -> str:
        return source_for(self.host)

    def url(self, path: str) -> str:
        return f"https://{self.host}{path}"


def source_for(host: str) -> str:
    """splms.polite.edu.sg → brightspace:splms"""
    return f"brightspace:{host.split('.')[0]}"


def _rich(obj: Any) -> str:
    """Rich text that may be nested ({Text: {Text, Html}, IsDisplayed}) or a plain string."""
    if isinstance(obj, str):
        return obj.strip()
    if not isinstance(obj, dict):
        return ""
    if isinstance(obj.get("Text"), dict):
        return rich_text(obj["Text"])
    return rich_text(obj)


def _attachments(objs: list[dict] | None) -> list[dict]:
    return [{"file_id": a.get("FileId"), "name": a.get("FileName"), "size": a.get("Size")} for a in objs or []]


def course_item(c: Course, raw: dict) -> ItemIn:
    access = raw.get("Access") or {}
    return ItemIn(
        source=c.source, kind="course", external_id=c.id, title=c.name, url=c.url(f"/d2l/home/{c.id}"),
        course_id=c.id, course_name=c.name, starts_at=access.get("StartDate"), ends_at=access.get("EndDate"),
        data={"code": c.code, "raw": raw},
    )


def assignment_item(c: Course, raw: dict, submissions: list[dict] | None = None) -> ItemIn:
    avail = raw.get("Availability") or {}
    data: dict[str, Any] = {
        "score_out_of": (raw.get("Assessment") or {}).get("ScoreDenominator"),
        "attachments": _attachments(raw.get("Attachments")),
        "links": [{"name": l.get("LinkName"), "href": l.get("Href")} for l in raw.get("LinkAttachments") or []],
        "is_group": raw.get("GroupTypeId") is not None,
        "grade_item_id": raw.get("GradeItemId"),
        "raw": raw,
    }
    if submissions is not None:
        # mysubmissions: [{Entity, Status, Feedback, Submissions: [{Id, SubmittedBy, SubmissionDate, Files}]}]
        dates = [s.get("SubmissionDate") for e in submissions for s in e.get("Submissions") or []]
        dates = sorted(d for d in dates if d)
        data["submitted"] = bool(dates)
        data["last_submitted_at"] = dates[-1] if dates else None
    return ItemIn(
        source=c.source, kind="assignment", external_id=f"{c.id}:{raw['Id']}", title=raw.get("Name") or "",
        body=rich_text(raw.get("CustomInstructions")),
        url=c.url(f"/d2l/lms/dropbox/user/folder_submit_files.d2l?db={raw['Id']}&ou={c.id}"),
        course_id=c.id, course_name=c.name, due_at=raw.get("DueDate"),
        starts_at=avail.get("StartDate"), ends_at=avail.get("EndDate"), data=data,
    )


def quiz_item(c: Course, raw: dict) -> ItemIn:
    time_limit = raw.get("TimeLimit") or {}
    attempts = raw.get("AttemptsAllowed") or {}
    body = "\n\n".join(t for t in (_rich(raw.get("Description")), _rich(raw.get("Instructions"))) if t)
    return ItemIn(
        source=c.source, kind="quiz", external_id=f"{c.id}:{raw['QuizId']}", title=raw.get("Name") or "",
        body=body, url=c.url(f"/d2l/lms/quizzing/user/quiz_summary.d2l?qi={raw['QuizId']}&ou={c.id}"),
        course_id=c.id, course_name=c.name, due_at=raw.get("DueDate"),
        starts_at=raw.get("StartDate"), ends_at=raw.get("EndDate"),
        data={
            "active": raw.get("IsActive"),
            "time_limit_min": time_limit.get("TimeLimitValue") if time_limit.get("IsEnforced") else None,
            "attempts": None if attempts.get("IsUnlimited") else attempts.get("NumberOfAttemptsAllowed"),
            "raw": raw,
        },
    )


def announcement_item(c: Course, raw: dict) -> ItemIn | None:
    if raw.get("IsHidden") or raw.get("IsPublished") is False:
        return None
    return ItemIn(
        source=c.source, kind="announcement", external_id=f"{c.id}:{raw['Id']}", title=raw.get("Title") or "",
        body=rich_text(raw.get("Body")), url=c.url(f"/d2l/le/news/{c.id}/{raw['Id']}/view"),
        course_id=c.id, course_name=c.name, occurred_at=raw.get("StartDate") or raw.get("CreatedDate"),
        ends_at=raw.get("EndDate"),
        data={"attachments": _attachments(raw.get("Attachments")), "pinned": bool(raw.get("PinnedDate")), "raw": raw},
    )


def walk_toc(toc: dict) -> list[tuple[list[str], dict]]:
    """Flatten /content/toc into (module path, topic) pairs."""
    out: list[tuple[list[str], dict]] = []

    def walk(module: dict, path: list[str]) -> None:
        here = [*path, module.get("Title") or ""]
        for t in module.get("Topics") or []:
            out.append((here, t))
        for m in module.get("Modules") or []:
            walk(m, here)

    for m in toc.get("Modules") or []:
        walk(m, [])
    return out


def content_item(c: Course, module_path: list[str], raw: dict) -> ItemIn | None:
    if raw.get("IsHidden"):
        return None
    tid = raw["TopicId"]
    return ItemIn(
        source=c.source, kind="content", external_id=f"{c.id}:{tid}", title=raw.get("Title") or "",
        body=_rich(raw.get("Description")), url=c.url(f"/d2l/le/content/{c.id}/viewContent/{tid}/View"),
        course_id=c.id, course_name=c.name, occurred_at=raw.get("LastModifiedDate"),
        due_at=raw.get("DueDate"), starts_at=raw.get("StartDateTime"), ends_at=raw.get("EndDateTime"),
        data={
            "type": raw.get("TypeIdentifier"),
            "module_path": module_path,
            "target": raw.get("Url"),
            "last_modified": raw.get("LastModifiedDate"),
            "raw": raw,
        },
    )


def event_item(c: Course, raw: dict) -> ItemIn:
    assoc = raw.get("AssociatedEntity") or None
    # Events tied to an assignment/quiz duplicate that item's due date; only
    # standalone events (tests, talks, deadlines set by hand) count as due.
    standalone = not (assoc and assoc.get("AssociatedEntityType"))
    return ItemIn(
        source=c.source, kind="event", external_id=f"{c.id}:{raw['CalendarEventId']}", title=raw.get("Title") or "",
        body=_rich(raw.get("Description")), url=raw.get("CalendarEventViewUrl"),
        course_id=c.id, course_name=c.name, due_at=raw.get("StartDateTime") if standalone else None,
        starts_at=raw.get("StartDateTime"), ends_at=raw.get("EndDateTime"),
        data={
            "all_day": raw.get("IsAllDayEvent"),
            "location": raw.get("LocationName"),
            "associated": {"type": assoc.get("AssociatedEntityType"), "id": assoc.get("AssociatedEntityId")}
            if not standalone else None,
            "raw": raw,
        },
    )


def grade_item(c: Course, raw: dict) -> ItemIn:
    return ItemIn(
        source=c.source, kind="grade", external_id=f"{c.id}:{raw['GradeObjectIdentifier']}",
        title=raw.get("GradeObjectName") or "", body=rich_text(raw.get("Comments")),
        url=c.url(f"/d2l/lms/grades/my_grades/main.d2l?ou={c.id}"), course_id=c.id, course_name=c.name,
        occurred_at=raw.get("ReleasedDate") or raw.get("LastModified"),
        data={
            "displayed": raw.get("DisplayedGrade"),
            "points": raw.get("PointsNumerator"),
            "out_of": raw.get("PointsDenominator"),
            "weighted": raw.get("WeightedNumerator"),
            "weighted_out_of": raw.get("WeightedDenominator"),
            "raw": raw,
        },
    )

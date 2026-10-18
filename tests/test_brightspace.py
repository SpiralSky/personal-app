import asyncio
from datetime import UTC, datetime

from campus_assistant.brightspace import normalize as N
from campus_assistant.brightspace.sync import CourseSync
from campus_assistant.config import Config
from campus_assistant.store import Store

COURSE = N.Course(host="splms.polite.edu.sg", id="997372", name="ST1522: BIG DATA TECHNOLOGIES")
NOW = datetime(2026, 10, 8, tzinfo=UTC)

FOLDER = {
    "Id": 55, "Name": "Lab2 Submission", "DueDate": "2026-10-30T10:00:00.000Z",
    "CustomInstructions": {"Text": "", "Html": "<p>Submit your <b>notebook</b></p>"},
    "Availability": {"StartDate": None, "EndDate": None}, "Attachments": [], "LinkAttachments": [],
    "Assessment": {"ScoreDenominator": 10}, "GroupTypeId": None, "TotalUsersWithSubmissions": 40,
}
QUIZ = {"QuizId": 7, "Name": "Quiz 1", "IsActive": True, "DueDate": None, "StartDate": "2026-10-10T00:00:00Z",
        "EndDate": "2026-10-12T00:00:00Z", "Description": {"Text": {"Text": "Covers T1-T3", "Html": ""}},
        "Instructions": {"Text": {"Text": "", "Html": ""}}, "TimeLimit": {"IsEnforced": True, "TimeLimitValue": 30},
        "AttemptsAllowed": {"IsUnlimited": False, "NumberOfAttemptsAllowed": 1}}
NEWS = [{"Id": 3, "Title": "Venue change", "Body": {"Text": "Lab moved to T2041", "Html": ""},
         "StartDate": "2026-10-07T01:00:00Z", "IsHidden": False, "IsPublished": True, "Attachments": []},
        {"Id": 4, "Title": "Draft", "Body": {"Text": "x"}, "IsHidden": True}]
TOC = {"Modules": [{"Title": "Week 1", "Topics": [
    {"TopicId": 900, "Title": "1_Big_Data_Concepts", "TypeIdentifier": "File",
     "Url": "/content/enforced/997372-ST1522-2620/Big_Data_Concepts_T1522.pdf",
     "LastModifiedDate": "2026-09-30T09:28:23.520Z", "IsHidden": False},
    {"TopicId": 901, "Title": "Lecture video", "TypeIdentifier": "File", "Url": "/content/x/lecture.mp4",
     "LastModifiedDate": "2026-09-30T09:28:23.520Z", "IsHidden": False},
], "Modules": [{"Title": "Practicals", "Topics": [
    {"TopicId": 902, "Title": "Prac1", "TypeIdentifier": "Link", "Url": "https://example.com",
     "LastModifiedDate": "2026-09-30T00:00:00Z"}]}]}]}
EVENTS = [
    {"CalendarEventId": 1, "Title": "Lab2 Submission - Due", "StartDateTime": "2026-10-30T10:00:00Z",
     "EndDateTime": "2026-10-30T10:00:00Z", "AssociatedEntity": {"AssociatedEntityType": "D2L.LE.Dropbox.Dropbox",
                                                                "AssociatedEntityId": 55}},
    {"CalendarEventId": 2, "Title": "Practical Test", "StartDateTime": "2026-11-05T02:00:00Z",
     "EndDateTime": "2026-11-05T04:00:00Z", "AssociatedEntity": None, "Description": "Bring laptop"},
]
GRADES = [{"GradeObjectIdentifier": "12", "GradeObjectName": "CA1", "DisplayedGrade": "18 / 20",
           "PointsNumerator": 18, "PointsDenominator": 20, "Comments": {"Text": "Good", "Html": ""}}]


class FakeClient:
    def __init__(self):
        self.submissions = []
        self.downloads = 0

    async def dropbox_folders(self, ou): return [FOLDER]
    async def my_submissions(self, ou, fid): return self.submissions
    async def quizzes(self, ou): return [QUIZ]
    async def news(self, ou): return NEWS
    async def toc(self, ou): return TOC
    async def calendar(self, ou, start, end): return EVENTS
    async def my_grades(self, ou): return GRADES

    async def topic_file(self, ou, tid):
        self.downloads += 1
        return b"%PDF-1.4 fake", "application/pdf", "Big_Data_Concepts_T1522.pdf"


def test_normalisers():
    a = N.assignment_item(COURSE, FOLDER, [])
    assert a.id == "brightspace:splms:assignment:997372:55"
    assert a.body == "Submit your notebook"
    assert a.due_at == "2026-10-30T10:00:00Z"
    assert a.data["submitted"] is False and a.data["score_out_of"] == 10

    q = N.quiz_item(COURSE, QUIZ)
    assert q.body == "Covers T1-T3" and q.data["time_limit_min"] == 30 and q.data["attempts"] == 1

    assert N.announcement_item(COURSE, NEWS[1]) is None
    paths = [(p, t["TopicId"]) for p, t in N.walk_toc(TOC)]
    assert paths[-1] == (["Week 1", "Practicals"], 902)

    linked, standalone = (N.event_item(COURSE, e) for e in EVENTS)
    assert linked.due_at is None and linked.data["associated"]["id"] == 55
    assert standalone.due_at == "2026-11-05T02:00:00Z"


def test_course_sync_end_to_end(tmp_path):
    cfg = Config(data_dir=tmp_path)
    cfg.ensure_dirs()
    store = Store(cfg.db_path)
    client = FakeClient()

    counts = asyncio.run(CourseSync(store, client, COURSE, cfg, NOW).run())
    assert counts["created"] == 1 + 1 + 1 + 3 + 2 + 1  # assignment, quiz, news, topics, events, grade
    assert counts["files"] == 1 and client.downloads == 1  # the .mp4 is skipped
    f = store.file_for("brightspace:splms:content:997372:900")
    assert f and open(f["path"], "rb").read() == b"%PDF-1.4 fake"

    # Second run: nothing changed, file not re-downloaded.
    counts = asyncio.run(CourseSync(store, client, COURSE, cfg, NOW).run())
    assert counts["created"] == 0 and counts["updated"] == 0 and client.downloads == 1

    # Student submits → reported as a named change.
    client.submissions = [{"Submissions": [{"Id": 1, "SubmissionDate": "2026-10-20T03:00:00Z"}]}]
    asyncio.run(CourseSync(store, client, COURSE, cfg, NOW).run())
    change = store.changes(include_created=False)[0]
    assert change["fields"] == ["data.last_submitted_at", "data.submitted"]

    # Assignment pulled from the course → soft-deleted.
    client.dropbox_folders = lambda ou: asyncio.sleep(0, result=[])
    asyncio.run(CourseSync(store, client, COURSE, cfg, NOW).run())
    assert store.get("brightspace:splms:assignment:997372:55")["deleted_at"] is not None


def test_session_expiry_is_detected_by_redirect_not_content_type():
    from types import SimpleNamespace

    from campus_assistant.brightspace.client import BrightspaceClient

    c = BrightspaceClient(request=None, host="splms.polite.edu.sg")
    resp = lambda url: SimpleNamespace(url=url)  # noqa: E731
    assert c._redirected_to_login(resp("https://login.microsoftonline.com/common/oauth2/authorize?x=1"))
    assert c._redirected_to_login(resp("https://splms.polite.edu.sg/d2l/login?target=%2Fd2l%2Fhome"))
    # An HTML course page served from the LMS itself is not a login page.
    assert not c._redirected_to_login(resp("https://splms.polite.edu.sg/d2l/api/le/1.99/1/content/topics/5/file"))

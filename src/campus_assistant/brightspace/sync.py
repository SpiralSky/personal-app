"""Pull everything relevant from each Brightspace host into the store."""

import hashlib
import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

from ..config import Config
from ..models import ItemIn, to_utc_iso
from ..store import ANY_COURSE, Store, now_iso
from ..text import safe_filename
from . import normalize as N
from .client import BrightspaceClient, SessionExpired
from .session import BrowserSession

log = logging.getLogger(__name__)

# File topics worth keeping locally (briefs, slides, specs, lecturer-written HTML pages). Videos etc. are skipped.
DOC_EXTENSIONS = {".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx", ".csv", ".txt", ".md", ".ipynb",
                  ".py", ".json", ".rtf", ".odt", ".odp", ".html", ".htm"}
ACTIVE_LOOKBACK = timedelta(days=30)   # a deadline this recent keeps a course "active"
CONTENT_LOOKBACK = timedelta(days=60)  # ...as does content modified this recently
SUBMISSION_LOOKBACK = timedelta(days=14)
CALENDAR_BACK, CALENDAR_AHEAD = timedelta(days=30), timedelta(days=180)


@dataclass
class SyncReport:
    started_at: str = field(default_factory=now_iso)
    finished_at: str | None = None
    hosts: dict[str, dict] = field(default_factory=dict)
    counts: Counter = field(default_factory=Counter)
    errors: list[str] = field(default_factory=list)
    login_required: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"started_at": self.started_at, "finished_at": self.finished_at, "hosts": self.hosts,
                "counts": dict(self.counts), "errors": self.errors, "login_required": self.login_required}


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def c_item_id(c: N.Course) -> str:
    return f"{c.source}:course:{c.id}"


def _later_of(item: ItemIn) -> str | None:
    dates = [d for d in (item.due_at, item.ends_at) if d]
    return max(dates) if dates else None


class CourseSync:
    def __init__(self, store: Store, client: BrightspaceClient, course: N.Course, cfg: Config, now: datetime):
        self.store, self.client, self.course, self.cfg, self.now = store, client, course, cfg, now
        self.counts: Counter = Counter()
        self.active = False
        self.errors: list[str] = []

    async def _fetch(self, what: str, coro):
        """Await one endpoint; a failure skips just that part of the course (None = don't touch stored items)."""
        try:
            return await coro
        except SessionExpired:
            raise
        except Exception as err:
            log.warning("%s / %s failed: %s", self.course.name, what, err)
            self.errors.append(f"{what}: {err}")
            return None

    def _save(self, kind: str, items: list[ItemIn], complete: bool = True) -> None:
        self.counts.update(self.store.upsert_many(items))
        if complete:
            self.counts["removed"] += self.store.mark_missing(
                self.course.source, kind, self.course.id, {i.id for i in items})

    def _mark_active(self, items: list[ItemIn]) -> None:
        cutoff = _iso(self.now - ACTIVE_LOOKBACK)
        if any((d := _later_of(i)) and d >= cutoff for i in items):
            self.active = True

    async def run(self) -> Counter:
        c, cl = self.course, self.client

        folders = await self._fetch("assignments", cl.dropbox_folders(c.id))
        if folders is not None:
            items = []
            sub_cutoff = _iso(self.now - SUBMISSION_LOOKBACK)
            for f in folders:
                probe = N.assignment_item(c, f)
                if (_later_of(probe) or "9999") >= sub_cutoff:
                    subs = await cl.my_submissions(c.id, f["Id"])
                    items.append(N.assignment_item(c, f, subs) if subs is not None else self._keep_submission(probe))
                else:
                    items.append(self._keep_submission(probe))
            self._mark_active(items)
            self._save("assignment", items)

        quizzes = await self._fetch("quizzes", cl.quizzes(c.id))
        if quizzes is not None:
            items = [N.quiz_item(c, q) for q in quizzes]
            self._mark_active(items)
            self._save("quiz", items)

        news = await self._fetch("news", cl.news(c.id))
        if news is not None:
            self._save("announcement", [i for n in news if (i := N.announcement_item(c, n))])

        toc = await self._fetch("content", cl.toc(c.id))
        topics: list[tuple[ItemIn, dict]] = []
        if toc is not None:
            for path, t in N.walk_toc(toc):
                if item := N.content_item(c, path, t):
                    topics.append((item, t))
            items = [i for i, _ in topics]
            self._mark_active(items)
            recent = _iso(self.now - CONTENT_LOOKBACK)
            if any((i.occurred_at or "") >= recent for i in items):
                self.active = True
            self._save("content", items)

        ms = lambda dt: dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")  # Valence rejects dates without milliseconds
        events = await self._fetch("calendar", cl.calendar(c.id, ms(self.now - CALENDAR_BACK), ms(self.now + CALENDAR_AHEAD)))
        if events is not None:
            # Events outside the window drop out of the response, so don't treat absence as removal.
            self._save("event", [N.event_item(c, e) for e in events], complete=False)

        grades = await self._fetch("grades", cl.my_grades(c.id))
        if grades is not None:
            self._save("grade", [N.grade_item(c, g) for g in grades])

        if self.active:
            await self._download_files(topics)
        return self.counts

    def _keep_submission(self, item: ItemIn) -> ItemIn:
        """Carry over submission status from the store when we skip re-checking it."""
        prev = self.store.get(item.id)
        if prev and "submitted" in prev["data"]:
            item.data["submitted"] = prev["data"]["submitted"]
            item.data["last_submitted_at"] = prev["data"].get("last_submitted_at")
        return item

    async def _download_files(self, topics: list[tuple[ItemIn, dict]]) -> None:
        max_bytes = self.cfg.max_file_mb * 1024 * 1024
        for item, raw in topics:
            if raw.get("TypeIdentifier") != "File":
                continue
            ext = Path((raw.get("Url") or "").split("?")[0]).suffix.lower()
            if ext not in DOC_EXTENSIONS:
                continue
            modified = to_utc_iso(raw.get("LastModifiedDate"))
            known = self.store.file_for(item.id)
            if known and known["source_modified"] == modified and Path(known["path"]).exists():
                continue
            got = await self.client.topic_file(self.course.id, raw["TopicId"])
            if not got:
                continue
            body, ctype, filename = got
            if len(body) > max_bytes:
                log.info("Skipping %s (%d MB)", item.title, len(body) // 2**20)
                continue
            filename = filename or Path(raw.get("Url") or item.title).name
            dest_dir = self.cfg.files_dir / self.course.source.split(":")[1] / self.course.id
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / f"{raw['TopicId']}_{safe_filename(filename)}"
            tmp = dest.with_suffix(dest.suffix + ".tmp")
            tmp.write_bytes(body)
            tmp.replace(dest)
            self.store.record_file(item.id, str(dest), filename, ctype, len(body),
                                   hashlib.sha256(body).hexdigest(), modified)
            self.counts["files"] += 1


async def sync_host(store: Store, session: BrowserSession, host: str, cfg: Config, report: SyncReport) -> None:
    client = await session.connect(host)
    now = datetime.now(UTC)
    skip = re.compile(cfg.bs_skip_courses, re.I) if cfg.bs_skip_courses else None
    enrollments = await client.my_courses()

    courses: list[tuple[N.Course, dict]] = []
    for e in enrollments:
        ou = e.get("OrgUnit") or {}
        if not (e.get("Access") or {}).get("CanAccess", True):
            continue
        course = N.Course(host=host, id=str(ou["Id"]), name=ou.get("Name") or "", code=ou.get("Code"))
        if skip and skip.search(course.name):
            continue
        courses.append((course, e))

    source = N.source_for(host)
    report.counts.update(store.upsert_many([N.course_item(c, raw) for c, raw in courses]))
    report.counts["removed"] += store.mark_missing(source, "course", ANY_COURSE, {c_item_id(c) for c, _ in courses})

    host_info = {"user": (client.user or {}).get("UniqueName"), "courses": len(courses), "active": []}
    for course, _ in courses:
        try:
            cs = CourseSync(store, client, course, cfg, now)
            report.counts.update(await cs.run())
            report.errors += [f"{host} / {course.name} / {e}" for e in cs.errors]
            if cs.active:
                host_info["active"].append(course.name)
        except SessionExpired:
            raise
        except Exception as err:
            log.exception("Course %s failed", course.name)
            report.errors.append(f"{host} / {course.name}: {err}")
    await session.save_cookies()
    report.hosts[host] = host_info


async def sync_brightspace(store: Store, cfg: Config, hosts: list[str] | None = None) -> SyncReport:
    report = SyncReport()
    async with BrowserSession(cfg, headless=True) as session:
        for host in hosts or cfg.bs_hosts:
            try:
                await sync_host(store, session, host, cfg, report)
            except SessionExpired:
                log.warning("%s: login required (run `campus login`)", host)
                report.login_required.append(host)
            except Exception as err:
                log.exception("Host %s failed", host)
                report.errors.append(f"{host}: {err}")
    report.finished_at = now_iso()
    return report

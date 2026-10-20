"""Thin async wrapper over Brightspace's Valence REST API.

Requests go through a Playwright APIRequestContext tied to a logged-in
browser context, so they carry the same session cookies the web UI uses.
GETs need no CSRF token or OAuth app registration.
"""

import asyncio
import logging
from typing import Any
from urllib.parse import urlencode, urlsplit

from playwright.async_api import APIRequestContext, APIResponse

log = logging.getLogger(__name__)


class SessionExpired(Exception):
    """The Brightspace session is gone; a manual `campus login` is needed."""


class BrightspaceClient:
    def __init__(self, request: APIRequestContext, host: str, delay: float = 0.25):
        self.request = request
        self.host = host
        self.delay = delay
        self.lp = "1.0"
        self.le = "1.0"
        self.user: dict | None = None

    def _url(self, path: str, params: dict | None = None) -> str:
        url = path if path.startswith("http") else f"https://{self.host}{path}"
        if params:
            url += ("&" if "?" in url else "?") + urlencode({k: v for k, v in params.items() if v is not None})
        return url

    async def _get(self, path: str, params: dict | None = None) -> APIResponse:
        url = self._url(path, params)
        for attempt in range(4):
            await asyncio.sleep(self.delay)
            resp = await self.request.get(url, headers={"Accept": "application/json"}, fail_on_status_code=False, timeout=30_000)
            if resp.status in (429, 502, 503, 504):
                wait = 5 * 2**attempt
                log.warning("%s → %s, retrying in %ss", path, resp.status, wait)
                await asyncio.sleep(wait)
                continue
            return resp
        return resp

    def _redirected_to_login(self, resp: APIResponse) -> bool:
        """An expired session redirects to the SSO/login page (another host or /d2l/login)."""
        url = urlsplit(resp.url)
        return url.netloc != self.host or url.path.startswith("/d2l/login")

    async def get_json(self, path: str, params: dict | None = None) -> Any | None:
        """JSON body, or None for 403/404 (no permission / tool not enabled in this course)."""
        resp = await self._get(path, params)
        if resp.status == 401 or self._redirected_to_login(resp):
            raise SessionExpired(self.host)
        if resp.status in (403, 404):
            return None
        ctype = resp.headers.get("content-type", "")
        if resp.ok and "json" not in ctype:
            raise RuntimeError(f"GET {path} returned {ctype or 'no content type'} instead of JSON")
        if not resp.ok:
            raise RuntimeError(f"GET {path} → {resp.status}: {(await resp.text())[:200]}")
        return await resp.json()

    # ── Session ─────────────────────────────────────────────────────────────
    async def check_session(self) -> bool:
        try:
            resp = await self._get("/d2l/api/lp/1.0/users/whoami")
        except Exception as exc:
            log.warning("check_session %s: %s", self.host, exc)
            return False
        if resp.ok and "json" in resp.headers.get("content-type", ""):
            self.user = await resp.json()
            return True
        return False

    async def load_versions(self) -> None:
        versions = await self.get_json("/d2l/api/versions/") or []
        latest = {v["ProductCode"]: v["LatestVersion"] for v in versions}
        self.lp = latest.get("lp", self.lp)
        self.le = latest.get("le", self.le)

    # ── Endpoints ───────────────────────────────────────────────────────────
    async def my_courses(self) -> list[dict]:
        items, bookmark = [], None
        while True:
            page = await self.get_json(f"/d2l/api/lp/{self.lp}/enrollments/myenrollments/",
                                       {"orgUnitTypeId": 3, "bookmark": bookmark})
            if not page:
                break
            items += page.get("Items") or []
            paging = page.get("PagingInfo") or {}
            if not paging.get("HasMoreItems"):
                break
            bookmark = paging.get("Bookmark")
        return items

    async def dropbox_folders(self, ou: str) -> list[dict] | None:
        return await self.get_json(f"/d2l/api/le/{self.le}/{ou}/dropbox/folders/")

    async def my_submissions(self, ou: str, folder_id: int) -> list[dict] | None:
        return await self.get_json(f"/d2l/api/le/{self.le}/{ou}/dropbox/folders/{folder_id}/submissions/mysubmissions/")

    async def quizzes(self, ou: str) -> list[dict] | None:
        out: list[dict] = []
        url: str | None = f"/d2l/api/le/{self.le}/{ou}/quizzes/"
        while url:
            page = await self.get_json(url)
            if page is None:
                return None if not out else out
            out += page.get("Objects") or []
            url = page.get("Next")
        return out

    async def news(self, ou: str) -> list[dict] | None:
        return await self.get_json(f"/d2l/api/le/{self.le}/{ou}/news/")

    async def toc(self, ou: str) -> dict | None:
        return await self.get_json(f"/d2l/api/le/{self.le}/{ou}/content/toc")

    async def calendar(self, ou: str, start: str, end: str) -> list[dict] | None:
        out: list[dict] = []
        bookmark = None
        while True:
            page = await self.get_json(f"/d2l/api/le/{self.le}/{ou}/calendar/events/myEvents/",
                                       {"startDateTime": start, "endDateTime": end, "bookmark": bookmark})
            if page is None:
                return None if not out else out
            out += page.get("Objects") or []
            nxt = page.get("Next")
            if not nxt:
                return out
            # Next is a full URL; reuse its bookmark.
            bookmark = dict(p.split("=", 1) for p in nxt.split("?", 1)[-1].split("&") if "=" in p).get("bookmark")
            if not bookmark:
                return out

    async def my_grades(self, ou: str) -> list[dict] | None:
        return await self.get_json(f"/d2l/api/le/{self.le}/{ou}/grades/values/myGradeValues/")

    async def topic_file(self, ou: str, topic_id: int) -> tuple[bytes, str | None, str | None] | None:
        """(body, content-type, filename) of a File topic."""
        resp = await self._get(f"/d2l/api/le/{self.le}/{ou}/content/topics/{topic_id}/file")
        if resp.status in (403, 404):
            return None
        if resp.status == 401 or self._redirected_to_login(resp):
            raise SessionExpired(self.host)
        if not resp.ok:
            raise RuntimeError(f"file {topic_id} → {resp.status}")
        # HTML is legitimate here: lecturers author pages as .html topics.
        ctype = resp.headers.get("content-type")
        filename = None
        disp = resp.headers.get("content-disposition", "")
        if "filename=" in disp:
            filename = disp.split("filename=", 1)[1].split(";")[0].strip().strip('"')
        return await resp.body(), ctype, filename

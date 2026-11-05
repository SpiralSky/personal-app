"""Brightspace sync / session-check / login orchestration, plus per-host auth state.

Everything that opens the browser profile goes through one lock: Chromium
refuses to open a profile that another instance is using.

Auth state per host (persisted in the store's meta table):
    ok              last check or sync succeeded
    login_required  the session is gone and silent SSO refresh failed
    unknown         never checked (e.g. no login yet)
A client (your central app) polls GET /auth/brightspace and, on
login_required, calls POST /auth/brightspace/login to open the sign-in window.
"""

import asyncio
import logging
from typing import Any

from .brightspace.client import SessionExpired
from .brightspace.session import BrowserSession
from .brightspace.sync import SyncReport, sync_brightspace
from .config import Config
from .store import Store, now_iso

log = logging.getLogger(__name__)

AUTH_KEY = "auth:brightspace"


class BrightspaceRunner:
    def __init__(self, store: Store, cfg: Config):
        self.store, self.cfg = store, cfg
        self.lock = asyncio.Lock()
        self.activity: str | None = None  # "sync" | "check" | "login" while running
        self.last_sync: SyncReport | None = None
        self.tasks: set[asyncio.Task] = set()
        self.after_sync: list = []  # callbacks run after each successful sync

    # ── Auth state ──────────────────────────────────────────────────────────
    def auth(self) -> dict[str, Any]:
        saved: dict = self.store.get_meta(AUTH_KEY, {})
        hosts = {h: saved.get(h) or {"state": "unknown"} for h in self.cfg.bs_hosts}
        states = {v["state"] for v in hosts.values()}
        overall = "login_required" if "login_required" in states else "unknown" if "unknown" in states else "ok"
        return {"state": overall, "hosts": hosts, "login_in_progress": self.activity == "login",
                "busy": self.activity}

    def _set_auth(self, host: str, state: str, user: str | None = None, detail: str | None = None) -> None:
        saved: dict = self.store.get_meta(AUTH_KEY, {})
        prev = saved.get(host) or {}
        entry = {"state": state, "user": user or prev.get("user"), "checked_at": now_iso(), "detail": detail}
        if state != prev.get("state"):
            entry["since"] = entry["checked_at"]
            log.info("Brightspace %s: %s → %s", host, prev.get("state", "unknown"), state)
        else:
            entry["since"] = prev.get("since", entry["checked_at"])
        saved[host] = entry
        self.store.set_meta(AUTH_KEY, saved)

    def _hosts_needing_login(self) -> list[str]:
        hosts = self.auth()["hosts"]
        return [h for h, v in hosts.items() if v["state"] != "ok"] or list(hosts)

    # ── Operations ──────────────────────────────────────────────────────────
    async def sync(self) -> SyncReport | None:
        if self.lock.locked():
            return None
        async with self.lock:
            self.activity = "sync"
            try:
                report = await sync_brightspace(self.store, self.cfg)
            except Exception as err:
                report = SyncReport(finished_at=now_iso(), errors=[f"Sync failed: {err}"])
                for host in self.cfg.bs_hosts:
                    self._set_auth(host, "unknown", detail="Sync could not start; inspect last_sync errors")
            finally:
                self.activity = None
            for host, info in report.hosts.items():
                self._set_auth(host, "ok", info.get("user"))
            for host in report.login_required:
                self._set_auth(host, "login_required", detail="Session expired; sign in again")
            self.last_sync = report
            self.store.set_meta("brightspace:last_sync", report.as_dict())
            log.info("Brightspace sync: %s", dict(report.counts))
            if report.hosts:
                for hook in self.after_sync:
                    hook(report)
            return report

    async def check(self) -> dict[str, Any]:
        """Verify each host's session (refreshing silently via SSO if possible) without syncing."""
        if self.lock.locked():
            return self.auth()
        async with self.lock:
            self.activity = "check"
            try:
                async with BrowserSession(self.cfg, headless=True) as session:
                    for host in self.cfg.bs_hosts:
                        try:
                            client = await session.connect(host)
                            self._set_auth(host, "ok", (client.user or {}).get("UniqueName"))
                        except SessionExpired:
                            self._set_auth(host, "login_required", detail="Session expired; sign in again")
                        except Exception as err:
                            log.warning("Session check for %s failed: %s", host, err)
                            self._set_auth(host, "unknown", detail=str(err))
            finally:
                self.activity = None
        return self.auth()

    async def login(self, hosts: list[str] | None = None, sync_after: bool = True) -> dict[str, Any]:
        """Open a visible sign-in window; sync afterwards if anything was signed in."""
        hosts = hosts or self._hosts_needing_login()
        async with self.lock:
            self.activity = "login"
            try:
                async with BrowserSession(self.cfg, headless=False) as session:
                    results = await session.interactive_login(hosts)
                for host, ok in results.items():
                    self._set_auth(host, "ok" if ok else "login_required",
                                   detail=None if ok else "Sign-in window closed or timed out")
            finally:
                self.activity = None
        if sync_after and any(results.values()):
            await self.sync()
        return self.auth()

    def spawn(self, coro) -> None:
        task = asyncio.create_task(coro)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    async def schedule_loop(self) -> None:
        # Syncs keep running while logged out: each attempt also tries a silent
        # SSO refresh, so a session can recover without the user.
        while True:
            if not self.cfg.cookie_jar.exists():
                for host in self.cfg.bs_hosts:
                    if self.auth()["hosts"][host]["state"] == "unknown":
                        self._set_auth(host, "login_required", detail="Never signed in")
            else:
                try:
                    await self.sync()
                except Exception:
                    log.exception("Scheduled sync failed")
            await asyncio.sleep(self.cfg.sync_interval_min * 60)


class AnalysisRunner:
    """Runs the LLM pipeline in the background after new data arrives.

    Requests that arrive while a run is in progress are coalesced into one
    follow-up run, so a burst of pushed emails doesn't queue many runs.
    """

    def __init__(self, store: Store, enabled: bool = True):
        self.store = store
        self.enabled = enabled
        self.running = False
        self.pending = False
        self.last: dict[str, Any] | None = None
        self.task: asyncio.Task | None = None

    def request(self, **kwargs: Any) -> bool:
        if not self.enabled:
            return False
        if self.running:
            self.pending = True
            return False
        self.task = asyncio.create_task(self._run(**kwargs))
        return True

    async def run_now(self, **kwargs: Any) -> dict[str, Any]:
        from .analysis.pipeline import Analyzer

        self.running = True
        try:
            started = now_iso()
            report = await Analyzer(self.store).run(**kwargs)
            self.last = {"started_at": started, "finished_at": now_iso(), **report}
            log.info("Analysis: %s", report)
            return self.last
        finally:
            self.running = False

    async def _run(self, **kwargs: Any) -> None:
        while True:
            self.pending = False
            try:
                await self.run_now(**kwargs)
            except Exception:
                log.exception("Analysis run failed")
            if not self.pending:
                return

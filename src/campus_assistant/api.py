"""Local HTTP API. Bound to 127.0.0.1 by default; there is no auth."""

import asyncio
import logging
import os
from collections import deque
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Literal

from .config import Config
from .ics import build_ics
from .mail import EmailBatch, email_item
from .models import IngestRequest
from .analysis.schemas import Category, Priority
from .runner import AnalysisRunner, BrightspaceRunner
from .store import Store

log = logging.getLogger(__name__)

RECENT_ERRORS: deque[dict] = deque(maxlen=200)


class RecentErrorsHandler(logging.Handler):
    def __init__(self):
        super().__init__(level=logging.WARNING)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            RECENT_ERRORS.append({
                "time": datetime.fromtimestamp(record.created, UTC).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
            })
        except Exception:
            self.handleError(record)


_bg_tasks: set[asyncio.Task] = set()


def create_app(cfg: Config | None = None, store: Store | None = None, schedule: bool = True,
               analyze: bool | None = None) -> FastAPI:
    root = logging.getLogger()
    if not any(isinstance(h, RecentErrorsHandler) for h in root.handlers):
        root.addHandler(RecentErrorsHandler())
    cfg = cfg or Config()
    cfg.ensure_dirs()
    store = store or Store(cfg.db_path)
    runner = BrightspaceRunner(store, cfg)
    if analyze is None:
        analyze = os.environ.get("CAMPUS_AUTO_ANALYZE", "1") != "0"
    analysis = AnalysisRunner(store, enabled=analyze)
    runner.after_sync.append(lambda report: analysis.request())

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        from .llm import PROVIDER_OVERRIDES, CUSTOM_PROVIDER_CONFIGS
        PROVIDER_OVERRIDES.update(store.get_meta("llm:provider_overrides", {}))
        CUSTOM_PROVIDER_CONFIGS.update(store.get_meta("llm:custom_provider_configs", {}))
        loop_task = asyncio.create_task(runner.schedule_loop()) if schedule else None
        yield
        if loop_task:
            loop_task.cancel()

    app = FastAPI(title="Campus Assistant", lifespan=lifespan)
    app.state.store, app.state.runner, app.state.cfg, app.state.analysis = store, runner, cfg, analysis

    @app.get("/health")
    def health():
        return {"ok": True}

    @app.get("/status")
    def status():
        return {"stats": store.stats(), "auth": {"brightspace": runner.auth()},
                "sync": {"busy": runner.activity,
                         "last": runner.last_sync.as_dict() if runner.last_sync else store.get_meta("brightspace:last_sync")},
                "analysis": {"auto": analysis.enabled, "running": analysis.running, "last": analysis.last}}

    # ── Ingest (used by the Outlook fork and any other pushers) ──────────────
    @app.get("/brightspace/status")
    def brightspace_status():
        observations = [dict(r) for r in store.conn.execute(
            "SELECT source, MAX(last_seen) AS last_seen FROM items "
            "WHERE source LIKE 'brightspace:%' GROUP BY source")]
        return {"auth": runner.auth(), "busy": runner.activity,
                "last_sync": store.get_meta("brightspace:last_sync"),
                "observations": observations,
                "counts": [r for r in store.stats() if r["source"].startswith("brightspace:")]}

    @app.post("/ingest")
    async def ingest(req: IngestRequest):
        counts = store.upsert_many(req.items)
        if counts.get("created") or counts.get("updated"):
            analysis.request()
        return {"received": len(req.items), **counts}

    @app.post("/ingest/email")
    async def ingest_email(batch: EmailBatch):
        items, errors = [], []
        for i, m in enumerate(batch.messages):
            try:
                items.append(email_item(m))
            except Exception as err:
                errors.append({"index": i, "error": str(err)})
        counts = store.upsert_many(items)
        if counts.get("created") or counts.get("updated"):
            analysis.request(briefs=False)
        return {"received": len(batch.messages), **counts, "errors": errors}

    # ── Reading ──────────────────────────────────────────────────────────────
    @app.get("/items")
    def items(source: str | None = None, kind: str | None = None, course_id: str | None = None,
              q: str | None = None, include_deleted: bool = False, raw: bool = False,
              limit: int = Query(100, le=1000), offset: int = 0):
        rows = store.query(source=source, kind=kind, course_id=course_id, q=q,
                           include_deleted=include_deleted, limit=limit, offset=offset)
        if not raw:
            for r in rows:
                r["data"].pop("raw", None)
        return rows

    @app.get("/items/{item_id:path}/history")
    def item_history(item_id: str):
        return store.history(item_id)

    @app.get("/items/{item_id:path}/file")
    def item_file(item_id: str):
        f = store.file_for(item_id)
        if not f or not Path(f["path"]).exists():
            raise HTTPException(404, "No downloaded file for this item")
        return FileResponse(f["path"], media_type=f["content_type"], filename=f["filename"])

    @app.get("/items/{item_id:path}")
    def item(item_id: str):
        row = store.get(item_id)
        if not row:
            raise HTTPException(404, "Not found")
        row["file"] = store.file_for(item_id)
        row["analyses"] = store.analyses_for(item_id)
        row["label"] = store.get_label(item_id)
        return row

    def _window(days: int, past_days: int) -> tuple[str, str]:
        """Return (start, end) ISO strings: past_days behind now to days ahead."""
        now = datetime.now(UTC)
        fmt = "%Y-%m-%dT%H:%M:%SZ"
        return (now - timedelta(days=past_days)).strftime(fmt), (now + timedelta(days=days)).strftime(fmt)

    @app.get("/upcoming")
    def upcoming(days: int = 30, overdue_days: int = 0):
        rows = store.upcoming(*_window(days, overdue_days))
        for r in rows:
            r["data"].pop("raw", None)
        return rows

    @app.get("/changes")
    def changes(since: str | None = None, limit: int = Query(200, ge=1, le=2000), include_created: bool = True,
                source: str | None = None, offset: int = Query(0, ge=0)):
        return store.changes(since=since, limit=limit, include_created=include_created, source=source, offset=offset)

    @app.get("/calendar.ics", response_class=PlainTextResponse)
    def calendar():
        body = build_ics(store.upcoming(*_window(365, 30)))
        return PlainTextResponse(body, media_type="text/calendar")

    # ── LLM analysis ────────────────────────────────────────────────────────
    @app.get("/triage")
    def triage(days: int = 14, categories: str | None = None, priorities: str | None = None,
               kinds: str | None = None, date_from: str | None = None, date_to: str | None = None,
               include_ignored: bool = False, needs_review: bool | None = None,
               category: str | None = None, priority: str | None = None, kind: str | None = None,
               limit: int = Query(200, le=1000)):
        """Triaged emails/announcements, newest first. Your labels override the model.

        categories, priorities, kinds: comma-separated values for multi-select filtering.
        date_from, date_to: ISO date strings (YYYY-MM-DD) for date range filtering.
        needs_review=true lists messages the classifier was unsure about and you haven't labelled;
        labelling them is what calibrates the cutoffs.
        """
        if date_from and date_to:
            since, until = date_from + "T00:00:00Z", date_to + "T23:59:59Z"
        elif date_from:
            since = date_from + "T00:00:00Z"
            until = None
        elif date_to:
            since = (datetime.now(UTC) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
            until = date_to + "T23:59:59Z"
        else:
            since = (datetime.now(UTC) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
            until = None

        categories, priorities, kinds = categories or category, priorities or priority, kinds or kind
        category_list = [c.strip() for c in categories.split(",")] if categories else None
        priority_list = [p.strip() for p in priorities.split(",")] if priorities else None
        kind_list = [k.strip() for k in kinds.split(",")] if kinds else None

        return store.triaged(since=since, until=until, categories=category_list, priorities=priority_list, kinds=kind_list,
                             include_ignored=include_ignored, needs_review=needs_review, limit=limit)

    @app.get("/tasks")
    def tasks(days: int = 60, overdue_days: int = 1):
        """Upcoming assignments/quizzes with their brief and plan (null until analysed)."""
        rows = store.upcoming(*_window(days, overdue_days), kinds=("assignment", "quiz"))
        for r in rows:
            r["data"].pop("raw", None)
            a = store.get_analysis(r["id"], "brief")
            r["brief"] = a["result"] if a else None
            r["brief_meta"] = {k: a[k] for k in ("provider", "model", "created_at", "error")} if a else None
        return rows

    @app.get("/triage/eval")
    def triage_eval(cutoff: float = 0.8):
        """Accuracy vs your labels, and whether classifier confidence means anything (per bucket)."""
        from .analysis.evaluate import evaluate
        return evaluate(store, cutoff)

    class Label(BaseModel):
        category: Category | None = None
        priority: Priority | None = None
        note: str | None = None

    @app.post("/items/{item_id:path}/label")
    def label(item_id: str, body: Label):
        """Correct the triage of one item. Stored separately; never overwritten by the model."""
        if not store.get(item_id):
            raise HTTPException(404, "Not found")
        store.set_label(item_id, body.category, body.priority, body.note)
        return store.get_label(item_id)

    class AnalyzeRequest(BaseModel):
        triage: bool = True
        briefs: bool = True
        since_days: int = 30
        horizon_days: int = 60
        limit: int | None = None
        force: bool = False

    @app.post("/analyze", status_code=202)
    async def run_analysis(req: AnalyzeRequest | None = None):
        req = req or AnalyzeRequest()
        if analysis.running:
            return {"started": False, "running": True}
        task = asyncio.create_task(analysis.run_now(**req.model_dump()))
        _bg_tasks.add(task)
        task.add_done_callback(_bg_tasks.discard)
        task.add_done_callback(
            lambda t: log.error("Background analysis failed: %s", t.exception())
            if not t.cancelled() and t.exception() else None
        )
        return {"started": True}

    @app.get("/llm/status")
    async def llm_status():
        from .llm import llm_status as status_of
        return await status_of()

    class ModelListRequest(BaseModel):
        endpoint: str
        api_key: str | None = None

    class CustomProviderConfig(BaseModel):
        endpoint: str
        model: str
        api_key: str | None = None
        thinking: bool = False

    class LLMProviderRequest(BaseModel):
        task: str
        preset: Literal["claude", "local", "auto", "off"] | None = None
        custom: CustomProviderConfig | None = None

    @app.get("/settings")
    async def get_settings():
        from .llm import LLMConfig, llm_status as status_of
        llm_cfg = LLMConfig()
        status = await status_of(llm_cfg)
        return {
            "llm": {
                "tasks": status["tasks"],
                "claude_model": llm_cfg.claude_model,
                "local_url": llm_cfg.local_url,
                "local_model": llm_cfg.local_model,
                "claude_credentials": status["claude_credentials"],
            },
            "config": {
                "bs_hosts": cfg.bs_hosts,
                "sync_interval_min": cfg.sync_interval_min,
                "browser_channel": cfg.browser_channel,
                "bs_skip_courses": cfg.bs_skip_courses,
            },
        }

    @app.post("/settings/llm")
    def set_llm_provider(req: LLMProviderRequest):
        from .llm import DEFAULT_PROVIDER, PROVIDER_OVERRIDES, CUSTOM_PROVIDER_CONFIGS
        if req.task not in DEFAULT_PROVIDER:
            raise HTTPException(404, f"Unknown task {req.task!r}")

        # Clear any previous custom config for this task
        CUSTOM_PROVIDER_CONFIGS.pop(req.task, None)

        if req.custom:
            CUSTOM_PROVIDER_CONFIGS[req.task] = {
                "endpoint": req.custom.endpoint,
                "model": req.custom.model,
                "api_key": req.custom.api_key,
                "thinking": req.custom.thinking,
            }
            PROVIDER_OVERRIDES.pop(req.task, None)
            store.set_meta("llm:provider_overrides", dict(PROVIDER_OVERRIDES))
            store.set_meta("llm:custom_provider_configs", dict(CUSTOM_PROVIDER_CONFIGS))
            return {"task": req.task, "provider": "custom", "config": req.custom.model_dump()}
        elif req.preset:
            PROVIDER_OVERRIDES[req.task] = req.preset
            store.set_meta("llm:provider_overrides", dict(PROVIDER_OVERRIDES))
            store.set_meta("llm:custom_provider_configs", dict(CUSTOM_PROVIDER_CONFIGS))
            return {"task": req.task, "provider": req.preset}
        else:
            raise HTTPException(400, "Must provide either 'preset' or 'custom'")

    @app.post("/settings/llm/models")
    async def get_llm_models(req: ModelListRequest):
        """Fetch available models from an OpenAI-compatible provider."""
        import httpx
        headers = {"Authorization": f"Bearer {req.api_key}"} if req.api_key else {}
        try:
            async with httpx.AsyncClient(timeout=10, headers=headers) as client:
                resp = await client.get(f"{req.endpoint.rstrip('/')}/models")
                resp.raise_for_status()
                data = resp.json()
                models = [m.get("id") for m in data.get("data", []) if m.get("id")]
                return {"models": models}
        except httpx.HTTPError as err:
            raise HTTPException(500, f"Failed to fetch models: {str(err)}")

    @app.get("/errors")
    def recent_errors():
        errors = list(reversed(RECENT_ERRORS))
        return {"errors": errors, "count": len(errors)}

    # ── Brightspace sync + auth ─────────────────────────────────────────────
    class LoginRequest(BaseModel):
        hosts: list[str] | None = None
        sync_after: bool = True

    @app.post("/sync/brightspace", status_code=202)
    async def trigger_sync():
        if runner.activity:
            return {"started": False, "busy": runner.activity}
        runner.spawn(runner.sync())
        return {"started": True}

    @app.get("/auth/brightspace")
    def auth_status():
        """Poll this: state is ok | login_required | unknown, overall and per host."""
        return runner.auth()

    @app.post("/auth/brightspace/check")
    async def auth_check():
        """Re-check sessions now (headless, tries silent SSO refresh). Takes a few seconds."""
        return await runner.check()

    @app.post("/auth/brightspace/login", status_code=202)
    async def auth_login(req: LoginRequest | None = None):
        """Open the sign-in window on this machine's display. Returns immediately; poll /auth/brightspace."""
        req = req or LoginRequest()
        if runner.activity == "login":
            return {"started": False, "login_in_progress": True}
        runner.spawn(runner.login(req.hosts, req.sync_after))
        return {"started": True}

    # ── Web UI (static build of web/) ───────────────────────────────────────
    index = cfg.web_dist / "index.html"
    if index.exists():
        if (cfg.web_dist / "assets").is_dir():
            app.mount("/ui/assets", StaticFiles(directory=cfg.web_dist / "assets"), name="ui-assets")

        @app.get("/", include_in_schema=False)
        def root():
            return RedirectResponse("/ui/")

        @app.get("/ui/{path:path}", include_in_schema=False)
        def ui(path: str):
            # Files at the dist root (favicon etc.); everything else is a client-side route.
            f = (cfg.web_dist / path).resolve()
            if path and f.is_file() and f.is_relative_to(cfg.web_dist.resolve()):
                return FileResponse(f)
            return FileResponse(index)

    return app

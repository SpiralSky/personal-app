# Backend Issues
_Files touched: src/campus_assistant/api.py, brightspace/, llm/, analysis/, kde/app/campus_kde.py_

## HIGH

- **No auth on API endpoints** — Deferred to the login system plan. API token approach agreed. Even localhost-only, any same-machine page can POST to `/analyze` or `/auth/brightspace/login`.

## MEDIUM

- **`brightspace/client.py`** — _fixed: added `timeout=30_000` to `self.request.get()` in `_get`_

## LOW

- **`api.py:141`** — _fixed: `_window` parameter renamed `include_overdue_days` → `past_days`; docstring added_
- **`analysis/pipeline.py`** — _stale: `Semaphore(CONCURRENCY=4)` and `MAX_LLM_PER_RUN` already in place_
- **`analysis/prompts.py`** — _stale: `PROMPT_VERSION` dict already exists and is documented_
- **Type hints** — Public methods in `store.py` and `create_app` in `api.py` already have return types. FastAPI route handler closures lack them but are low value (FastAPI handles serialization). Resolved.

## Done (this session)

- **`api.py:298`** — API key moved from URL query param to POST body (both backend and frontend).
- **`api.py:226–232`** — `asyncio.create_task` fire-and-forget fixed; task stored in `_bg_tasks`, error-logging callback attached.
- **`session.py`** — Cookie storage migrated to `keyring` library (cross-platform; file fallback retained). `keyring` added to `pyproject.toml`.
- **`api.py:68`** — `PROVIDER_OVERRIDES` / `CUSTOM_PROVIDER_CONFIGS` now persisted to SQLite `meta` table; restored on startup.
- **`brightspace/client.py:73`** — `check_session` bare `except Exception` now logs the error.
- **`session.py:64`** — `except Exception: pass` in `__aexit__` now logs a warning.
- **`config.py:22–24`** — Env vars now wrapped in `field(default_factory=...)` so they're read at instantiation, not class definition time.
- **`pipeline.py:99`** — Raw SQL calls moved into `Store.triage_items()`, `Store.content_file_rows()`, `Store.content_link_rows()`.
- **`pipeline.py:225`** — `json.loads(l["path"])` wrapped in `try/except json.JSONDecodeError`.
- **`documents.py:58–59`** — Cache invalidation switched from `mtime` to sha256 sidecar file (`.txt-extract.hash`).
- **`brightspace/client.py`** — added `timeout=30_000` to Playwright requests.
- **`api.py:141`** — `_window` parameter renamed + docstring.

# Changelog

All notable changes to campus-assistant are recorded here.
Format loosely follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## Unreleased

### Added
- `pytest-cov` with 60 % line-coverage threshold enforced in CI
- Vitest unit-test suite (`web/src/`) with initial tests for `format.ts`
- GitHub Actions CI: backend-test, frontend-test, frontend-build, frontend-lint
- `GET /health` probe endpoint (`{"ok": true}`)
- Error boundary in `App.tsx`; dismissable error banner via `NotifyErrorCtx`
- `Settings.tsx` save feedback and inline error display
- `pyrightconfig.json` — Pyright type-checker configured for `src/` and `tests/`
- `.env.example` — authoritative template for all `CAMPUS_*` environment variables
- `src/campus_assistant/_logging.py` — shared log format and level config

### Changed
- `pyproject.toml` dependency pins switched from `>=` to `~=` (compatible-release)
- `setup.sh` — re-enabled npm audit (`--no-audit` removed)
- `research_notes/` and `reports/` excluded from git via `.gitignore`
- Cookie storage migrated from plain file to `keyring`
- `PROVIDER_OVERRIDES` / `CUSTOM_PROVIDER_CONFIGS` persisted to SQLite

### Fixed
- `asyncio.create_task` fire-and-forget — task now stored and error-logged
- `brightspace/client.py` — added `timeout=30 000 ms` to Playwright requests
- `documents.py` — cache invalidation switched to sha256 sidecar
- `api.py` — API key moved from URL query param to POST body

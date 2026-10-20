# Infrastructure & Project Issues
_Cross-cutting: CI/CD, testing, deps, config, project structure_

## HIGH

- ~~**No CI/CD**~~ — _fixed: `.github/workflows/ci.yml` with 4 jobs: backend-test (pytest), frontend-test (vitest), frontend-build (tsc+vite), frontend-lint (eslint)_
- ~~**No frontend tests**~~ — _fixed: Vitest installed, `vitest.config.ts` added, 12 tests for `format.ts`_
- ~~**No coverage tooling**~~ — _fixed: `pytest-cov` added to dev deps; `.coveragerc` omits cli/kde_app; 60% threshold enforced in CI and via `--cov-fail-under`. Current: 66%._

## MEDIUM

- ~~**`pyproject.toml`**~~ — _fixed: all `>=` pins switched to `~=` (compatible-release) to block unexpected major-version jumps_
- ~~**No `.env.example`**~~ — _fixed: `.env.example` created from `config.py`; documents all `CAMPUS_*` env vars with defaults_
- ~~**No type checker configured**~~ — _fixed: `pyrightconfig.json` added; `typeCheckingMode: standard`, covers `src/` and `tests/`_
- ~~**`setup.sh`**~~ — _fixed: `--no-audit` removed from `npm ci`; CVE scanning re-enabled_
- ~~**`HANDOFF.md` committed**~~ — _fixed: removed from git history via filter-repo, added to `.gitignore`_
- ~~**No structured logging standard**~~ — _fixed: `src/campus_assistant/_logging.py` with `configure_logging(verbose)` used by CLI; consistent format `%(asctime)s %(levelname)s %(name)s: %(message)s`_

## LOW

- ~~No `CHANGELOG.md` or `CONTRIBUTING.md`~~. — _fixed: both files created_
- ~~`research_notes/` and `reports/` in the repo~~. — _fixed: both dirs added to `.gitignore`_
- ~~`setup.sh` is not idempotent~~. — _stale: all steps (`uv sync`, `npm ci`, `playwright install`) are already idempotent; service install is gated behind `--service` flag_
- ~~No lightweight `GET /health → {"ok": true}` endpoint~~ — _stale: already existed at `api.py:76`_

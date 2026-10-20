# Infrastructure & Project Issues
_Cross-cutting: CI/CD, testing, deps, config, project structure_

## HIGH

- ~~**No CI/CD**~~ — _fixed: `.github/workflows/ci.yml` with 4 jobs: backend-test (pytest), frontend-test (vitest), frontend-build (tsc+vite), frontend-lint (eslint)_
- ~~**No frontend tests**~~ — _fixed: Vitest installed, `vitest.config.ts` added, 12 tests for `format.ts`_
- **No coverage tooling** — `pytest-cov` not in dev deps; no `.coveragerc` or threshold. Coverage unknown and unchecked.

## MEDIUM

- **`pyproject.toml`** — Lower-bound-only pins (`>=`). `uv.lock` is committed (good), but `uv lock --upgrade` can jump to a breaking major with no signal. Use `~=` (compatible-release) specifiers.
- **No `.env.example`** — No authoritative template for contributors; README text and actual `config.py` keys can drift apart.
- **No type checker configured** — No `pyrightconfig.json` or `mypy.ini`; `py.typed` marker exists but nothing enforces types locally or in CI.
- **`setup.sh`** — Passes `--no-audit` to npm; silently skips CVE scanning on frontend deps.
- ~~**`HANDOFF.md` committed**~~ — _fixed: removed from git history via filter-repo, added to `.gitignore`_
- **No structured logging standard** — Log format, level config, and correlation IDs unspecified across the backend service.

## LOW

- No `CHANGELOG.md` or `CONTRIBUTING.md`.
- `research_notes/` and `reports/` in the repo will accumulate and inflate history. Better in a wiki or separate branch.
- `setup.sh` is not idempotent; re-running can break an existing install.
- No lightweight `GET /health → {"ok": true}` endpoint for monitoring tools (current `/status` returns data, not a probe target).

# Infrastructure & Project Issues
_Cross-cutting: CI/CD, testing, deps, config, project structure_

## HIGH

- **No CI/CD** — No `.github/workflows/` or equivalent. Lint, test, and build never run automatically. Regressions land silently.
- **No frontend tests** — `package.json` has no test script, no Vitest/Jest config. All 9 pages have zero automated coverage.
- **No coverage tooling** — `pytest-cov` not in dev deps; no `.coveragerc` or threshold. Coverage unknown and unchecked.

## MEDIUM

- **`pyproject.toml`** — Lower-bound-only pins (`>=`). `uv.lock` is committed (good), but `uv lock --upgrade` can jump to a breaking major with no signal. Use `~=` (compatible-release) specifiers.
- **No `.env.example`** — No authoritative template for contributors; README text and actual `config.py` keys can drift apart.
- **No type checker configured** — No `pyrightconfig.json` or `mypy.ini`; `py.typed` marker exists but nothing enforces types locally or in CI.
- **`setup.sh`** — Passes `--no-audit` to npm; silently skips CVE scanning on frontend deps.
- **`HANDOFF.md` committed** — Contains local paths, dev planning notes, DB backup locations. Not appropriate for version-controlled history; move to a local scratch file or gitignore it.
- **No structured logging standard** — Log format, level config, and correlation IDs unspecified across the backend service.

## LOW

- No `CHANGELOG.md` or `CONTRIBUTING.md`.
- `research_notes/` and `reports/` in the repo will accumulate and inflate history. Better in a wiki or separate branch.
- `setup.sh` is not idempotent; re-running can break an existing install.
- No lightweight `GET /health → {"ok": true}` endpoint for monitoring tools (current `/status` returns data, not a probe target).

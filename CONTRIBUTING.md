# Contributing

## Prerequisites

- Python 3.14+ and [uv](https://docs.astral.sh/uv/)
- Node.js 20+ and npm
- `./setup.sh` — installs Python deps, Playwright Chromium, and builds the web UI

## Development workflow

```bash
# Backend tests (with coverage)
uv run pytest

# Frontend tests
cd web && npm test

# Type-check (Python)
uv run pyright

# Lint (frontend)
cd web && npm run lint

# Run the dev server
uv run campus serve
```

## Branch and commit conventions

- Branch names: `fix/<short-name>` or `feat/<short-name>`
- Commit subject: imperative, ≤ 72 chars (e.g. `fix: add timeout to Playwright requests`)
- Add a body after a blank line when the *why* isn't obvious from the subject
- One logical change per commit; squash fixups before merging
- Merge to `master` only when the branch is clean and all CI checks pass
- Never push directly to `master`

## Issue tracking

Open issues are kept in `.claude/issues/` (`backend.md`, `frontend.md`, `infra.md`).
Mark items done inline rather than deleting them.

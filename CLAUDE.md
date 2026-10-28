## Feature spec authorship

- Feature specs in `specs/features/` are **owner-authored**. Agents may scaffold structure, ask clarifying questions, check consistency and edit wording on request, but must not invent feature behaviour, defaults, priorities, rules or acceptance criteria.
- `F-004` is intentionally an empty scaffold; the owner will author it in a new session. Do not fill it in on your own initiative.
- Naming: hybrid `F-NNN-feature-name.md`; keep the ID in the metadata table, not the H1. See `specs/features/README.md`.

## Git practices

- **Branch per task**: `fix/<short-name>` for bug fixes, `feat/<short-name>` for new features. Work never goes directly on `master`.
- **Commit messages**: imperative subject line ≤ 72 chars (e.g. `fix: add timeout to Playwright requests`). Add a body after a blank line when the why isn't obvious.
- **One logical change per commit.** Squash fixups before merging.
- **Merge to `master`** only when the branch is clean and tested.
- **Issue tracking**: keep `.claude/issues/backend.md`, `frontend.md`, `infra.md` up to date — mark items done inline rather than deleting them.

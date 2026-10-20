@/home/spiralsky/projects/workflow-experiments/framework/prompt/.system.intent.md

## Git practices

- **Branch per task**: `fix/<short-name>` for bug fixes, `feat/<short-name>` for new features. Work never goes directly on `master`.
- **Commit messages**: imperative subject line ≤ 72 chars (e.g. `fix: add timeout to Playwright requests`). Add a body after a blank line when the why isn't obvious.
- **One logical change per commit.** Squash fixups before merging.
- **Merge to `master`** only when the branch is clean and tested.
- **Issue tracking**: keep `.claude/issues/backend.md`, `frontend.md`, `infra.md` up to date — mark items done inline rather than deleting them.

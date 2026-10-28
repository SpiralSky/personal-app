# Plans

Working plans for the spec-driven rewrite. The roadmap is
[spec-roadmap.md](spec-roadmap.md); architecture decisions the agent makes
autonomously are logged in [decisions.md](decisions.md).

Read this file before acting on a spec. It defines what the agent may decide
alone and what must go to the owner.

## Autonomy policy

The owner is consulted **only about feature behaviour**. Architecture,
implementation, storage, libraries, process layout and testing mechanics are
the agent's call.

### Decide and proceed (do not ask)

- Architecture and implementation choices: package layout, module boundaries,
  class design, SQLite schema details, indexes, PRAGMAs, WAL, migration
  mechanics, serialization formats, retry/backoff values, latency budgets,
  cache layout, blob paths, concurrency primitives.
- Library and tooling choices (within the accepted feature constraints), e.g.
  encryption library, PDF text extraction, HTTP client, test framework.
- API/internal contract *implementation* details that do not change documented
  behaviour: OpenAPI generation, enum representation, pagination internals.
- Writing/fixing code, tests, CI, docs, and non-normative spec wording
  (typos, cross-links, section numbering, source labels).
- Corpus hygiene: fixing INDEX counts and links, normalising status values,
  adding missing required sections as empty scaffolds, adding compatibility
  sections that only describe already-decided behaviour.
- Logging every non-trivial architecture decision in
  [decisions.md](decisions.md) with context/alternatives/consequence.
- Git: branch per task (`feat/…`, `fix/…`, `docs/…`), small logical commits,
  squash fixups, merge to `master` once clean and tested.

### Stop and ask the owner (feature gate)

- Any new or changed **functional rule (FR)**, **acceptance criterion (AC)**,
  default, precedence, priority, scope, non-goal, or user-visible flow.
- Data retention/export policy, privacy/egress rules, consent flows, trust
  thresholds, UX wording that changes meaning, surface tiering, auth UX.
- Resolving a contradiction between owner-authored specs.
- Promoting a spec to **Accepted** or declaring a feature **Implemented**.
- Anything where two reasonable readings would produce different user-visible
  behaviour.
- If a question is genuinely architecture-only, **decide it and note it** — do
  not spend owner attention on it.

Questions are batched per spec (see roadmap "Ask owner" blocks) and sent as a
short numbered list with a recommended default, so the owner can answer with
one-word approvals.

### Per-spec workflow

1. **Audit** — read the spec, its dependencies, the relevant part of
   `docs/codebase-assessment.md`, and the architecture baseline. Produce a gap
   list.
2. **Hygiene** — agent fixes structure/wording/index. No feature invention.
3. **Feature gate** — send the owner only the open feature questions, with
   recommended defaults. Wait for answers; record them in the spec's change log
   and mark `Source: owner`.
4. **Acceptance** — update FRs/ACs, resolve OPEN items, check against the
   architecture spec, then ask the owner to accept (single yes/no).
5. **Implement** — set status `Implementing`, branch, implement in vertical
   slices, tests alongside.
6. **Verify** — run the spec's test plan, check every AC, then ask the owner to
   mark `Implemented`. Update INDEX and issue trackers.

Never implement against a Draft spec whose FRs are still `proposal`-sourced.

## Current repo state

`specs/`, `plans/`, `docs/` and the updated `CLAUDE.md`/`README.md` are committed
on branch `docs/spec-baseline` (commit `95b9533`), pending review and merge.
Phase 0 is complete except the owner answer to G0-Q1 (F-004 authorship) and
confirmation of G0-Q2 (F-001 status). Start there before touching F-004.

`python scripts/check_specs.py` is the structural gate; it currently exits 0
with warnings (missing sections in Draft specs, F-001's empty scaffolds).
CI runs it non-blocking until `--strict` is clean.

# Agent architecture decisions

Append-only log of decisions the agent made without asking the owner. One entry
per non-trivial choice. If a decision turns out to constrain feature behaviour,
stop and raise it as a feature question instead.

Format:

```md
## AD-YYYYMMDD-NN — <decision>

- **Status:** proposed | accepted | superseded
- **Context:** what forced the choice
- **Decision:** what was chosen
- **Alternatives:** what was rejected and why
- **Consequences:** what becomes hard later
- **Affects:** F-NNN, A-NNN
```

Promote decisions that are hard to reverse into `specs/architecture/ADR-NNN-*.md`
and link them here.

---

## AD-20261028-01 — SQLite (one database per service) with forward-only migrations

- **Status:** accepted (promoted to [ADR-001](../specs/architecture/ADR-001-sqlite-and-migrations.md))
- **Context:** every spec assumed SQLite but stored DDL and migration behaviour in feature prose; two services need separate stores.
- **Decision:** WAL, `foreign_keys=ON`, `busy_timeout=10000`, `PRAGMA user_version`, numbered transactional forward-only migrations, `VACUUM INTO` snapshot before apply, no ORM-owned schema.
- **Alternatives:** PostgreSQL/DuckDB (violates local-first), Alembic (hides the DDL A-001 owns), down-migrations (snapshot restore is the rollback).
- **Consequences:** rollback = snapshot restore; no cross-database joins; pre-migration snapshot must be integrity-checked.
- **Affects:** F-002, F-003, F-005, F-006, F-007, F-013, F-018, F-019.

## AD-20261028-02 — Brightspace crawler is a separate distributable service

- **Status:** accepted (promoted to [ADR-002](../specs/architecture/ADR-002-crawler-as-separate-service.md))
- **Context:** F-019 Q-4 left packaging open (standalone vs submodule vs in-process); F-004 assumes a loopback service.
- **Decision:** own Python distribution (`campus-crawler`), own systemd unit, own data dir, own SQLite database, `/v1` REST + MCP; main app proxies and never imports it or reads its DB.
- **Alternatives:** in-process module (crash/lock coupling, Playwright in the daemon), git submodule (no independent install), runtime plugin (shared process).
- **Consequences:** two installs/upgrade paths; no SQL joins across the boundary; adapter + contract tests required.
- **Affects:** F-004, F-019, F-016, F-018.

## AD-20261028-03 — Local API security: loopback + provenance + principals + scoped credentials

- **Status:** accepted (promoted to [ADR-003](../specs/architecture/ADR-003-local-api-security-model.md))
- **Context:** F-001 (Accepted) requires lock screen/RBAC; F-015 (Draft) declares auth a non-goal; F-016 adds a `.daemon-token`; F-013 requires MCP auth.
- **Decision:** layer the model instead of picking one: loopback transport, Host/Origin validation on every request, explicit principals (`owner`/`student`/`agent`/`guest`) with a server-side role matrix, session cookie for the UI, 0600 `.daemon-token` for the CLI, per-surface tokens for KDE/widget/ICS, bearer token + provenance for HTTP MCP.
- **Alternatives:** Origin/Host only (protects the browser origin, not a person at a shared machine); full OAuth/OIDC (out of scope, no cloud identity); separate auth systems per surface (drift).
- **Consequences:** every route needs a minimum role and a test; F-015 NG-1 must be amended before F-015 is accepted (owner-visible).
- **Affects:** F-001, F-013, F-015, F-016, F-004, F-018.

## AD-20261028-04 — Canonical sync routes on `/api/v1/sources/brightspace/*`

- **Status:** accepted
- **Context:** G0-5 drift — F-015 says `POST /api/v1/brightspace/sync`, F-004 says `/api/v1/sources/brightspace/sync`, F-016/F-001 ACs say `/api/v1/sync/run`.
- **Decision:** F-004's `sources/brightspace/*` family is canonical (F-004 is Accepted and owns the integration). `/api/v1/brightspace/*` and `/api/v1/sync/run` return 307 aliases for v1.0; aliases inherit the target route's authorisation. Crawler-side `POST /v1/sync` is unaffected.
- **Alternatives:** adopt F-015's path (contradicts the Accepted F-004 route table and job-status route), adopt `/sync/run` (loses the per-source namespace).
- **Consequences:** F-015's table and F-016's AC are updated in their own phases; no feature behaviour changes.
- **Affects:** F-001, F-004, F-015, F-016, F-019.

## AD-20261028-05 — Canonical `items` schema follows F-002, not F-003's legacy DDL

- **Status:** accepted
- **Context:** F-002 (Accepted) defines `body_text`/`body_html` and includes `course_id` in the content hash; F-003 §8.1 (Draft) has a single `body` column and omits `course_id`.
- **Decision:** A-001 §7.2 is the schema authority: `body_text TEXT NOT NULL`, `body_html TEXT`, `course_id` hashed; F-003's table is updated when F-003 is accepted (Phase 1, step 4).
- **Alternatives:** keep the legacy single `body` column (loses rich rendering and contradicts the canonical contract); dual-write `body` as a generated column (needless legacy surface).
- **Consequences:** F-003's DDL prose becomes a pointer to A-001; hash parity tests must cover the field list.
- **Affects:** F-002, F-003, F-006, F-007.

## AD-20261028-06 — `analyses` is defined in A-001 and shared by three features

- **Status:** accepted
- **Context:** F-003, F-006 and F-007 each assumed an `analyses` table with different tasks; no single definition existed.
- **Decision:** one table in A-001 §7.2 (`item_id`, `task` ∈ `triage|brief`, `input_hash`, `provider`, `model`, `result`, `error`, `usage`, `created_at`; PK `(item_id, task)`), with the F-003 FR-6/FR-7 invalidation contract.
- **Alternatives:** separate tables per feature (duplicated invalidation logic); a generic key-value cache (loses typed columns).
- **Consequences:** crawler-sourced items are never keyed into this table by FK; their analyses are re-derived at the proxy boundary.
- **Affects:** F-003, F-006, F-007.

## AD-20261028-07 — Corpus structure is checked by `scripts/check_specs.py`, initially non-blocking

- **Status:** accepted
- **Context:** status values, INDEX counts and required sections drifted repeatedly; prose review does not catch it.
- **Decision:** stdlib script validates statuses, INDEX counts/rows, required sections, FR/AC definitions and links; errors fail, warnings do not; CI job `spec-check` runs with `continue-on-error: true` until the warnings are resolved.
- **Alternatives:** hand review (already failed); blocking from day one (blocks the baseline on pre-existing gaps).
- **Consequences:** promote to required once `--strict` is clean; F-018's missing ACs remain visible as warnings.
- **Affects:** all specs.

# Runtime contracts and persistence

| Field | Value |
|---|---|
| ID | A-001 |
| Status | Accepted |
| Owner | engineering (agent-maintained; behaviour delegated to feature specs) |
| Created | 2026-10-28 |
| Last updated | 2026-10-28 |
| Supersedes | — |
| Superseded by | — |

> **Authority.** This is the architecture baseline: structure, contracts and
> persistence. It defines **how** the system is built, never **what** the
> product does. Feature behaviour stays in `specs/features/`; where this file
> and an accepted feature spec disagree about behaviour, the feature spec wins.
> Schema and route shapes here are authoritative for implementation.
>
> **Evidence rule.** Claims marked **[target]** are decisions not yet verified
> by code or tests. Claims marked **[current]** were observed in the existing
> implementation (`docs/codebase-assessment.md`). Nothing here is trusted as
> "done" without a test or contract check (see §14).

---

## 1. Context and constraints

- **Product shape:** local-first student academic workstation; one user, one
  machine, no cloud backend (F-001 NG-1/NG-2).
- **Runtime:** Python 3.14 daemon (`campus serve`) exposing an embedded React
  SPA and a versioned REST API on loopback; a CLI (`campus`) that proxies to the
  daemon or runs in-process (F-001 §8.2, F-016).
- **Data plane:** a standalone Brightspace crawler daemon (ADR-002) and local
  email ingestion (F-005), both feeding a canonical item model (F-002).
- **Storage:** SQLite, WAL, forward-only migrations (ADR-001).
- **Offline:** ingestion, search, triage and briefs must work without network;
  only LLM calls and crawler sync may require connectivity, and both degrade
  explicitly (F-001 G-1, F-013).
- **Platforms:** Linux/systemd Tier 1; macOS/launchd and WSL2 Tier 2 (F-001 §10).
  No native mobile apps, no public hosting.
- **Constraints:** idle daemon < 90 MB RSS, HTTP ready < 1.2 s cold start
  (F-001 §11); Playwright only in the crawler process, never in the daemon.

## 2. Quality attributes

| Attribute | Target | Verification |
|---|---|---|
| Privacy | no egress without anonymizer; no telemetry; loopback only | unit tests on the egress guard, network-isolated e2e |
| Reliability | ingestion idempotent; a crawler outage never corrupts main data | integration tests with crawler down/slow |
| Recoverability | every migration preceded by a verified snapshot; restore drill | F-018 test plan |
| Performance | API p95 < 100 ms for list reads on 10⁵ items; FTS search < 50 ms | benchmark in CI (target) |
| Maintainability | one dependency rule (§5), no SQL outside repositories, generated API client | import-linter / review checklist |
| Testability | every FR has at least one AC-linked test; contracts tested from OpenAPI | §14 gates |
| Accessibility | keyboard-only triage and lock screen; focus management | web e2e + axe checks (F-006 §10) |

## 3. System boundaries

Inside:

- `campus_assistant` daemon (HTTP API, background runners, store, LLM adapters,
  MCP server), React SPA, `campus` CLI.
- `campus-crawler` service (Playwright crawling, its own store, REST/MCP).
- Local email ingestion (drop-dir + CLI import adapters, F-005).

Outside:

- Public networking, cloud sync, mobile apps, multi-tenant identity
  (F-001 NG-1–NG-4).
- The institution's LMS and mail servers — read/write only through their public
  interfaces, never a database mirror.
- Third-party LLM providers — optional, anonymised, never authoritative stores.

## 4. Component model

```text
                 +--------------------------------------------+
   Browser SPA --|  Transport (FastAPI routers, /api/v1)      |
   CLI/daemon ---|  Auth + provenance middleware (ADR-003)    |
   MCP client ---|  MCP server (stdio, HTTP/SSE)              |
                 +------------------+-------------------------+
                                    | application services
        +---------------------------+----------------------------+
        | ingestion | change log | triage | briefs | search    |
        | settings  | backup     | sync proxy | calendar       |
        +---------------------------+----------------------------+
                                    | ports (protocols)
        +-------------------+-------+--------+-------------------+
        | repositories      | LLM adapters   | crawler HTTP      |
        | (SQLite, blobs)   | (provider)     | client            |
        +-------------------+----------------+-------------------+
                                    |
              SQLite (campus-assistant.db) + blobs/ (ADR-001)
```

- **Domain** — canonical `Item`, taxonomy, change/hash rules, triage schema,
  brief schema (F-002, F-003, F-006, F-007). Pure Python + Pydantic, no I/O.
- **Application services** — orchestrate ports; own transactions and budgets.
- **Ports/adapters** — repository (SQLite), blob store (filesystem), LLM
  provider adapters (Claude/OpenAI/Gemini/local, F-013), crawler client (HTTP),
  clock, keyring/vault.
- **Transport** — FastAPI routers, MCP server, CLI. Translates HTTP/JSON ↔
  application calls; contains no business rules.
- **UI** — React SPA; consumes only the API.

The crawler is a peer service with the same internal layering, its own
persistence and its own `/v1` contract (ADR-002, F-019).

## 5. Dependency rule

`transport → application → domain`; `application → ports ← adapters`.

- `domain` imports nothing outside the standard library and Pydantic.
- `application` imports `domain` and ports, never adapters or transport.
- `adapters` import domain models and external libraries, never transport.
- `transport` imports application services and schemas, never repositories
  directly.
- No module outside `adapters/` executes SQL or touches the filesystem blob
  store.
- The crawler is imported by nothing in `campus_assistant`; the only coupling is
  the HTTP client in `adapters/crawler/`.

## 6. Contracts

### 6.1 Versioning and envelope

- Canonical endpoints live under `/api/v1/`; non-API routes are `/` (SPA),
  `/calendar.ics`, `/api/openapi.json` (F-015 FR-1/FR-2, FR-3).
- Success (single object): `{ "data": { ... } }`.
- Success (list): `{ "data": [...], "meta": { "total", "limit", "offset", "has_more" } }`
  (F-015 §6.2).
- Error: `{ "error": { "code", "message", "details", "timestamp" } }` (F-015 §6.3).
- Error codes: `item_not_found` 404, `file_not_found` 404, `crawler_unavailable`
  503, `crawler_auth_required` 401, `validation_error` 422, `origin_forbidden`
  403, `payload_too_large` 413, `malformed_json` 400, `unsupported_media_type`
  415, `unauthorized` 401, `forbidden` 403, `conflict` 409, `rate_limited` 429.
- Payload limits: 2 MB JSON default; 35 MB for `/api/v1/ingest/email` (F-015 FR-10).
- `GET /api/openapi.json` is generated from the routers (OpenAPI 3.1) and is the
  single source for the generated TypeScript client. Hand-written client types
  are prohibited; CI diffs the generated artefacts (§14).

### 6.2 Route table (canonical)

Role abbreviations per ADR-003: `O` owner, `S` student, `A` agent, `G` guest;
`anon` only where stated. Every route inherits provenance checks (§9).

| Method | Path | Role | Spec |
|---|---|---|---|
| GET | `/api/v1/health` | anon | F-015 |
| POST | `/api/v1/auth/login` | anon | F-001 |
| POST | `/api/v1/auth/logout` | S+ | F-001 |
| GET | `/api/v1/auth/session` | S+ | F-001 |
| GET | `/api/v1/status` | S+ | F-015 |
| GET | `/api/v1/items` | S+ | F-015 |
| GET | `/api/v1/items/{id}` | S+ | F-015 |
| GET | `/api/v1/items/{id}/history` | S+ | F-003 |
| GET | `/api/v1/items/{id}/changes` | S+ | F-003 |
| GET | `/api/v1/changes` | S+ | F-003 |
| POST | `/api/v1/items/{id}/label` | S+ | F-015 |
| PUT | `/api/v1/labels/{item_id}` | S+ | F-006 |
| GET | `/api/v1/upcoming` | G+ | F-015 |
| GET | `/api/v1/triage` | S+ | F-006 |
| POST | `/api/v1/triage/run` | S+ | F-006 |
| GET | `/api/v1/triage/eval` | S+ | F-006 |
| GET | `/api/v1/tasks` | A+ | F-007 |
| GET | `/api/v1/tasks/{item_id}/brief` | A+ | F-007 |
| POST | `/api/v1/tasks/{item_id}/brief/run` | S+ | F-007 |
| PUT | `/api/v1/tasks/{item_id}/plan` | A+ | F-007 |
| POST | `/api/v1/tasks/{item_id}/plan/step/{step_idx}/toggle` | A+ | F-007 |
| POST | `/api/v1/ingest/email` | S+ | F-005 |
| GET | `/api/v1/files/{sha256}` | S+ | F-005/F-015 |
| GET | `/api/v1/sources/brightspace/status` | S+ | F-004 |
| POST | `/api/v1/sources/brightspace/sync` | S+ | F-004 |
| GET | `/api/v1/sources/brightspace/sync/{job_id}` | S+ | F-004 |
| GET | `/api/v1/sources/brightspace/courses` | S+ | F-004 |
| GET | `/api/v1/sources/brightspace/items` | S+ | F-004 |
| POST | `/api/v1/sources/brightspace/login` | O | F-004 |
| GET | `/api/v1/settings/llm` | O | F-013 |
| PUT | `/api/v1/settings/llm` | O | F-013 |
| POST | `/api/v1/settings/llm/keys` | O | F-013 |
| POST | `/api/v1/settings/llm/probe` | O | F-013 |
| GET | `/api/v1/mcp/sse` | A | F-013 |
| POST | `/api/v1/mcp/messages` | A | F-013 |
| GET | `/calendar.ics` | G (feed token) | F-012 |
| GET | `/api/openapi.json` | anon | F-015 |

**Compatibility aliases (307, deprecated at v1.0):** `/api/v1/brightspace/status`,
`/api/v1/brightspace/sync` → `sources/brightspace/*`; `/api/v1/sync/run` →
`/api/v1/sources/brightspace/sync`; legacy unversioned routes `/items`, `/status`,
`/triage`, `/upcoming`, `/changes`, `/ingest/email` → their `/api/v1` target
(F-015 §11). Aliases inherit the target's authorisation.

Rationale for the canonical sync path: F-004 (Accepted) already defines
`/api/v1/sources/brightspace/*`; F-015's table, F-016's AC and F-001's AC name
older paths. This reconciles the drift without changing feature behaviour
(G0-5). Recorded as AD-20261028-04 in `plans/decisions.md`.

### 6.3 Crawler contract (consumed, not defined here)

The main app consumes the crawler's `/v1` API (F-019 §9.1) and maps its item
shape to the canonical `Item`. Timeouts: 30 s for reads, 5 s for status; errors
map to `crawler_unavailable`. The crawler contract is frozen by F-019 before
F-004 is implemented.

## 7. Data model and persistence

### 7.1 Canonical entity: `Item`

`Item` is the single domain object shared by ingestion, storage, API and UI
(F-002 §8.1). Fields: `id` (`"{source}:{kind}:{external_id}"`), `source`, `kind`,
`external_id`, `title`, `body_text`, `body_html` (nullable), `url`, `course_id`,
`course_name`, `occurred_at`, `due_at`, `starts_at`, `ends_at`,
`data: dict`. Timestamps are UTC ISO-8601 text. `body` is a deprecated read-only
alias for `body_text`.

`content_hash` = SHA-256 over normalised sorted JSON of `title`, `body_text`,
`body_html`, `url`, `course_id`, `course_name`, `occurred_at`, `due_at`,
`starts_at`, `ends_at`, and `data` with the ephemeral keys `raw`, `meta` and
`last_crawled` removed (F-002 FR-9/FR-10, F-003 FR-1/FR-2). Whitespace-only
changes to `title` are not meaningful (F-003 FR-3).

**Reconciliation:** F-003 §8.1's legacy DDL has a single `body` column and omits
`course_id` from the hash. F-002 is Accepted and authoritative; the schema below
therefore has `body_text` + `body_html` and hashes `course_id`. F-003's table is
updated when F-003 is accepted (Phase 1, step 4).

### 7.2 Main database DDL

```sql
PRAGMA foreign_keys = ON;      -- per connection
PRAGMA journal_mode = WAL;     -- per database
PRAGMA synchronous = NORMAL;
PRAGMA busy_timeout = 10000;

CREATE TABLE items (
    id            TEXT PRIMARY KEY,
    source        TEXT NOT NULL,
    kind          TEXT NOT NULL,
    external_id   TEXT NOT NULL,
    title         TEXT NOT NULL DEFAULT '',
    body_text     TEXT NOT NULL DEFAULT '',
    body_html     TEXT,
    url           TEXT,
    course_id     TEXT,
    course_name   TEXT,
    occurred_at   TEXT,
    due_at        TEXT,
    starts_at     TEXT,
    ends_at       TEXT,
    data          TEXT NOT NULL DEFAULT '{}',
    content_hash  TEXT NOT NULL,
    first_seen    TEXT NOT NULL,
    last_seen     TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    deleted_at    TEXT
);
CREATE INDEX idx_items_source_kind ON items(source, kind);
CREATE INDEX idx_items_due ON items(due_at) WHERE deleted_at IS NULL;
CREATE INDEX idx_items_updated ON items(updated_at);

CREATE TABLE item_history (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id      TEXT NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    content_hash TEXT NOT NULL,
    snapshot     TEXT NOT NULL,
    replaced_at  TEXT NOT NULL
);
CREATE INDEX idx_history_item ON item_history(item_id, replaced_at DESC);

CREATE TABLE changes (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id TEXT NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    at      TEXT NOT NULL,
    change  TEXT NOT NULL CHECK (change IN ('created','updated','removed','restored')),
    fields  TEXT NOT NULL DEFAULT '[]'
);
CREATE INDEX idx_changes_at ON changes(at DESC);

CREATE TABLE analyses (
    item_id    TEXT NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    task       TEXT NOT NULL CHECK (task IN ('triage','brief')),
    input_hash TEXT NOT NULL,
    provider   TEXT NOT NULL,
    model      TEXT,
    result     TEXT,
    error      TEXT,
    usage      TEXT,
    created_at TEXT NOT NULL,
    PRIMARY KEY (item_id, task)
);
CREATE INDEX idx_analyses_task ON analyses(task, created_at);

CREATE TABLE labels (
    item_id    TEXT PRIMARY KEY REFERENCES items(id) ON DELETE CASCADE,
    category   TEXT NOT NULL,
    priority   TEXT NOT NULL,
    note       TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

Ownership of `analyses`: F-006 §8.2 defines it; F-007 stores briefs under
`task='brief'`. **Invalidation contract**
(F-003 FR-6/FR-7): an `updated` change purges analyses for the item; an update
touching only `data.folder` or `url` does not invalidate content-based analyses.
Because crawler-sourced items are not stored in this database (ADR-002),
invalidation for them is the crawler's responsibility and is re-derived at the
proxy boundary; the main app never caches a crawler item's analysis by foreign
key.

`labels` is human ground truth for calibration (F-006). It is never written by
the cascade; a mismatch between `labels` and `analyses.result` is surfaced, not
silently reconciled (F-006 Q-2).

### 7.3 Crawler database

Owned by F-019 §8.1: `hosts`, `courses`, `items` (crawler-local shape with
`raw`), `discussions`, `checklists`/`checklist_items`, `blobs`, `file_refs`,
`file_extractions`, `audit_log`, and contentless FTS5 `fts_search`. Same PRAGMAs
as §7.2, `busy_timeout = 10000` for writers. The main app never reads this file.

### 7.4 Blobs

- Main app: `<data>/blobs/sha256/<first2>/<next2>/<sha256>`; content-addressed
  on the filesystem with no separate blob table; served at
  `/api/v1/files/{sha256}` with the stored content type. Attachments ≤ 25 MB
  (F-005).
- Download/write path: write to `.tmp.<uuid>`, verify size + SHA-256, then
  atomic rename into place (F-019 §7; same rule for email attachments).
- Crawler: `~/.local/share/campus-crawler/blobs/sha256/…` (F-019 §5.2);
  orphan purge after a 14-day grace period (F-019 FR-15).
- F-018's reference to `documents/` and `attachments/` trees is superseded by
  the single `blobs/` tree; the backup manifest must name what it actually
  includes (flagged for F-018 in Phase 4).

### 7.5 Schema changes

Numbered forward-only migrations; `PRAGMA user_version` is the version;
transactional; snapshot before apply (ADR-001, §15).

## 8. Configuration and secrets

- **Directories** (F-001 FR-001-07): data `$XDG_DATA_HOME/campus-assistant`
  (default `~/.local/share/campus-assistant`), config
  `$XDG_CONFIG_HOME/campus-assistant`, cache `$XDG_CACHE_HOME/campus-assistant`.
  Crawler uses its own data dir (`CRAWLER_DATA_DIR`).
- **Config file:** `$XDG_CONFIG_HOME/campus-assistant/config.toml` (single
  loader, TOML, validated at startup). Runtime-mutable settings that the UI
  edits (LLM providers/tasks, anonymization, session timeout, schedules) live in
  the `meta` table as JSON (`config:llm`, `config:sync`, …) so they survive
  restarts and backups.
- **Precedence:** CLI flag > environment variable > `meta`/config file > default.
- **LLM config shape:** F-013 §7.1 (`secret_storage_mode`, `anonymization`,
  `providers`, `tasks`), validated by Pydantic. Unknown provider `type` is a
  startup error, not a silent skip.
- **Secrets:** API keys via OS keyring by default, AES-256-GCM encrypted SQLite
  vault (`cryptography`, Argon2id/PBKDF2 ≥ 100 000 iterations) when keyring is
  unavailable (F-013 FR-013-05/06). Environment variables
  (`ANTHROPIC_API_KEY`, …) take precedence for the session (FR-013-08). Secrets
  never appear in logs, GET responses or backups.
- **Machine credentials:** `.daemon-token` (0600) for CLI; per-surface tokens
  stored hashed. Crawler sessions stay under the crawler's own data dir.
- **Crawler config:** `~/.local/share/campus-crawler/config.json` (F-019 §5.2).

## 9. Lifecycle and concurrency

### 9.1 Startup and shutdown

1. Load and validate config; open the database; run pending migrations (after a
   snapshot); verify `integrity_check` on the post-migration DB.
2. Start background runners **after** the HTTP listener is bound and health
   reports ready (F-001 §8.1, AC-001-01).
3. On `SIGTERM`: stop accepting requests, cancel/await runners with a bounded
   grace period (10 s), close SQLite cleanly, exit 0.
4. Startup failure is fatal and logged with a machine-readable reason
   (`config_invalid`, `migration_failed`, `db_locked`, `port_in_use`).

### 9.2 Process model

- One `campus serve` daemon per user, `systemd --user`, `Restart=always`
  (F-001 §8.1). One writer process; SQLite transactions are short and
  application-level locks are not used for correctness where a transaction
  suffices.
- Background runners: scheduled crawler sync (F-004 §6.3), email drop-dir watch
  (F-005), background indexing/brief generation (F-007). Each runner has one
  owner and coalesces duplicate triggers (a running sync returns the existing
  `job_id`; a triage run returns 409 `conflict`).
- CLI dispatch (F-016): if `GET /health` succeeds, proxy over HTTP with the
  `.daemon-token`; otherwise run in-process, taking the same migrations and
  transactions. Both paths must produce identical JSON output.
- Resource limits: one Playwright session per host, owned by the crawler; the
  daemon holds no browser state.
- Backups/restore take an exclusive maintenance lock (F-018): API returns 503
  with a `maintenance` reason; runners pause.

### 9.3 Concurrency rules

- Writes in a single transaction; never hold a transaction open across a
  network call (LLM/crawler). Compute outside, then write.
- Long jobs report progress by job id; cancellation is cooperative and leaves
  cached data intact (F-019 FR-18).
- Rate/backoff for outbound calls: exponential, initial 2 s, factor 2, jitter
  ±20 %, max 3 retries (F-019 §7); budgets per run
  (`MAX_CLASSIFY`, `MAX_LLM`, F-006).

## 10. Error handling and observability

- **Error taxonomy:** domain errors are typed (`NotFound`, `Conflict`,
  `ValidationFailed`, `CrawlerUnavailable`, `CrawlerAuthRequired`,
  `PrivacyEgressBlocked`, `VaultDecryptionError`, `BudgetExhausted`) and mapped
  once in the transport layer to the §6.1 envelope. Unexpected exceptions map to
  500 with a correlation id and never leak stack traces to the client.
- **Logging:** structured JSON to stderr (journald under systemd); optional
  rotating file in `$XDG_STATE_HOME/campus-assistant/logs/`. Fields: `ts`,
  `level`, `event`, `component`, `request_id`, `job_id`, plus redacted context.
  Secrets, API keys, email bodies and credentials are never logged.
- **Persisted events:** user-visible failures may be persisted for the System
  view (F-014, Baseline) with retention defined there; crawler mutations are
  always written to its immutable `audit_log` (F-019 FR-10).
- **Health:** `GET /api/v1/health` → `{status, version, db:
  {ok, schema_version}, crawler: {reachable, state}}`; `degraded` is a valid
  state, not a 500. `/api/v1/status` adds counts and runner state.
- **Metrics:** no external telemetry; counters are exposed via status endpoints
  only.

## 11. Security and privacy

Full model: [ADR-003](ADR-003-local-api-security-model.md).

- Loopback bind only; Host/Origin validation on every request; explicit
  principals (`owner`/`student`/`agent`/`guest`) and a server-side role matrix
  (§6.2); session inactivity lock (default 15 min).
- CLI uses `.daemon-token` (0600); MCP HTTP uses a bearer token **and**
  provenance checks; `/calendar.ics` uses a feed token.
- No egress without the anonymizer; fail closed with
  `PrivacyEgressBlockedError`; local providers produce zero egress.
- Download endpoints require authentication and validate content type; no path
  traversal (`sha256` is strictly hex). HTTP responses set
  `X-Content-Type-Options: nosniff`, a restrictive CSP for the SPA, and
  `Referrer-Policy: no-referrer`.
- Backups exclude secrets (`F-018`), and exported data is user-initiated only.

## 12. Frontend architecture

- React + TypeScript + Vite + Tailwind (F-001 §5.1), served as static assets by
  the daemon; no SSR.
- **Data access:** a generated TypeScript client from `/api/openapi.json`
  (F-015 FR-3). No `fetch` calls with hand-written shapes; no direct SQLite
  access (F-001 FR-001-05).
- **Routing:** SPA routes mirror the seven product areas (F-008, Baseline):
  Today, Inbox, Tasks, Browse, Sources, System, Settings. Route guards redirect
  to the lock screen when the session is absent or expired.
- **State:** server state is cached per query key and invalidated by mutation
  events; optimistic updates only for label/triage actions, with rollback on
  error.
- **Accessibility:** keyboard-only triage (F-006 §10), visible focus, ARIA live
  regions for background job progress, reduced-motion support.
- **Error/empty/loading states** are first-class per feature spec; components do
  not invent copy for missing features.

## 13. Packaging and deployment

- **Developer:** `uv sync`; `uv run campus serve`; Vite dev server proxying
  `/api` to the daemon. Web build artefacts are committed only as release
  assets, not source.
- **Install:** `uv tool install .` for the daemon/CLI; a self-contained Linux
  AppImage bundles the built SPA (F-001 G-4). The crawler is installed
  separately (`uv tool install campus-crawler`) per ADR-002.
- **Services:** `campus-assistant.service` (F-001 §8.1) and
  `campus-crawler.service`, both `systemd --user`, both `Restart=always`.
  macOS uses `launchd` equivalents; Windows is supported via WSL2 only.
- **Update path:** package upgrade replaces code; the daemon migrates on next
  start after snapshotting. Crawler and daemon are upgraded independently; the
  main app treats an older crawler as `degraded`, not broken.
- **Uninstall:** data and config directories are left in place; removal is an
  explicit documented command (F-018 export before delete).

## 14. Testing strategy and CI gates

| Layer | What | Gate |
|---|---|---|
| Unit | domain invariants (hash, taxonomy, normalisation), matching/ranking, budget logic | pytest, required |
| Repository | DDL applies from empty; migrations idempotent; FK/cascade behaviour | pytest + temporary DB |
| Integration | API before/after, ingestion idempotency, crawler down/slow, vault failure, egress blocked | pytest, required |
| Contract | `/api/openapi.json` snapshot; generated TS client in sync; route table (§6.2) matches routers; every route has a role | **[target]** `scripts/check_api_contract.py` (not yet written) |
| Web | type-check + build (`web/npm run build`), Vitest units, Playwright e2e for lock screen + triage | CI required |
| Specs | status values, required sections, unique IDs, INDEX counts, links | `scripts/check_specs.py` (non-blocking until G0-6 is green, then required) |
| Eval | triage calibration on a labelled fixture set (F-006 §6.3) | scheduled/nightly, not a merge gate |

- Coverage floor rises with implementation; the current 60 % floor stays until
  F-002/F-003 land, then is re-baselined. Coverage is a floor, not evidence:
  every AC must name a concrete test.
- No gate relies on prose. A claim in a spec without a test is marked
  **[target]** here.

## 15. Migration and rollback

- **Database:** forward-only migrations (ADR-001), `user_version`, snapshot
  before apply, `integrity_check` after. Rollback = restore the snapshot
  (F-018 restore flow).
- **Legacy API:** unversioned routes and superseded names return 307 to their
  canonical target for v1.0 (F-015 §11, §6.2 here). Removal is a v1.1 decision.
- **Legacy crawler coupling:** in-process Playwright scraping in
  `campus_assistant/brightspace/` is removed when F-004 is implemented; until
  then it stays the fallback and is never extended (F-004 §11).
- **Data export/import:** portable JSON export + SQLite snapshot (F-018);
  migration to a new machine is restore-then-verify, not a re-crawl.
- **Cutover:** a migration that cannot complete transactionally aborts startup;
  the previous version remains runnable against the snapshot.

## 16. Decision log

| Record | Decision |
|---|---|
| [ADR-001](ADR-001-sqlite-and-migrations.md) | SQLite per service, WAL, forward-only migrations, no ORM-owned schema |
| [ADR-002](ADR-002-crawler-as-separate-service.md) | Crawler is a separate distributable service with its own store and `/v1` API |
| [ADR-003](ADR-003-local-api-security-model.md) | Loopback + provenance + explicit principals + scoped credentials |
| `plans/decisions.md` AD-20261028-04 | Sync triggers canonicalised on `/api/v1/sources/brightspace/*`, older paths aliased |

Open architecture items (raised to the owner, not decided here):

- F-001's RBAC vs F-015 NG-1 ("no auth") — resolved in ADR-003 on the
  architecture side; F-015 must be amended before acceptance.
- F-003's legacy `body` column and `course_id` hash omission — resolved here in
  favour of F-002; F-003 to be updated in its Phase 1 step.
- F-018 backup tree naming (`documents/`/`attachments/` vs `blobs/`) — F-018 is
  Draft; §7.4 is the intended layout.

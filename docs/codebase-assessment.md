# Codebase assessment

**Project:** `personal-app` / `campus-assistant`
**Snapshot:** `4596d3b` on `feat/coverage-tooling` (working tree clean at time of review)
**Reviewed:** 2026-10-25
**Purpose:** establish a factual baseline before a possible spec-first rewrite.

> **How to use this document.** Read this first, then the [feature spec index](../specs/features/INDEX.md) and the [spec conventions](../specs/README.md). This document describes the **current implementation**. Feature specs in `specs/features/` describe **desired behaviour** and may override what is described here. Where this assessment and a feature spec disagree, the feature spec wins — that is intentional.

---

## 1. Executive summary

This is a **well-kept solo prototype**, not yet a clean system architecture.

At the file level it is organised and readable: clear domain packages, small modules, good docstrings, meaningful tests for the tricky logic, and operational documentation that is better than most hobby projects. At the system level the important contracts are implicit and already drifting between the backend, the React UI, the KDE tray app and the Plasma widget.

The code is small enough to rewrite: roughly **3.8k lines of Python**, **2.2k lines of TypeScript/CSS**, and **0.8k lines of tests**. The real risk is not volume; it is **extracting the behaviour that currently lives in SQL, dict keys, prompts and tests** and freezing it in a specification before replacing the implementation.

**Verdict:** a spec-first rewrite is defensible. Do it as a parallel/strangler rebuild with contract tests and a data migration, not as a big-bang deletion.

| Dimension | Score | Summary |
|---|---:|---|
| Module layout | 4/5 | Clear domain packages; mostly small files; imports essentially acyclic |
| Readability | 4/5 | Good docstrings, section comments, naming |
| Type/contract rigour | 2/5 | Dicts and raw rows end-to-end; no response models; hand-written TS types |
| Config / dependency injection | 2/5 | Env read at import, mutation and request time; mutable process globals |
| Persistence | 2.5/5 | Strong change-tracking design; no migrations, repository boundary or FK constraints |
| Tests | 3/5 | Good core coverage; **suite is red**; boundaries and UI largely untested |
| Tooling / CI | 2/5 | Build/lint pass; Python type-check absent; CI would fail |
| Docs / traceability | 2/5 | Strong README; changelog and issue tracker contain false “fixed” claims |
| Frontend | 3/5 | Clean primitives; large pages, duplicated API shapes, minimal tests |
| **Overall** | **~6/10 prototype, ~4/10 foundation** | Tidy to read, expensive to evolve |

---

## 2. Review method and scope

Reviewed:

- All first-party source under `src/`, `web/src/`, `kde/`, `tests/`, and project configuration.
- Project docs: `README.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, `.claude/issues/*`, `.env.example`.
- Git history and tracked/ignored file state.

Executed:

| Check | Result |
|---|---|
| Backend tests (`.venv/bin/python -m pytest -q`) | **45 passed, 1 failed**, 65.8% coverage |
| Frontend tests (`npm test`) | **12 passed** |
| Frontend build (`npm run build`) | **Passed** |
| Frontend lint (`npm run lint`) | **Passed**, 1 warning |
| API probes with `TestClient` | Confirmed triage filter and model-list method mismatches |
| Pyright | **Not run** — not installed or declared |

Not tested: real Brightspace/SSO flows, a real local LLM server, the Claude API, KDE/Plasma runtime, packaging into an installed wheel.

---

## 3. Architecture at a glance

The current application is a **local modular monolith**:

```text
Brightspace (Valence API + Playwright session) ─┐
Outlook archive / POST /ingest/email ───────────┤
                                                 ▼
                                            SQLite store
                                     (items, history, changes,
                                      analyses, labels, files)
                                                 │
                       ┌─────────────────────────┼─────────────────────────┐
                       ▼                         ▼                         ▼
                 FastAPI JSON API          CLI (`campus`)           Background runners
                       │                                                 │
          ┌────────────┼────────────┐                         sync scheduler + analysis
          ▼            ▼            ▼
      React web     KDE tray      Plasma widget
```

### 3.1 Source layout

| Area | Files | Responsibility |
|---|---|---|
| Core | `models.py`, `store.py`, `config.py`, `text.py`, `ics.py` | Canonical item, SQLite persistence, configuration, text/calendar helpers |
| Sources | `brightspace/`, `mail.py` | Login/session, Valence client, normalisation, sync, email import |
| Intelligence | `analysis/`, `llm/` | Triage/briefs, prompts, schemas, documents, evaluation, providers |
| Runtime | `runner.py`, `service.py`, `api.py`, `cli.py` | Background orchestration, systemd unit, HTTP API, CLI |
| Web | `web/src/` | React UI: Today, Inbox, Tasks, Browse, Sources, Settings, System, Errors |
| Desktop | `kde/` | PySide6 tray app, Plasma widget, launcher/install scripts |

Python module sizes are mostly 40–230 lines. The outliers are [store.py](../src/campus_assistant/store.py) (433), [api.py](../src/campus_assistant/api.py) (385) and [pipeline.py](../src/campus_assistant/analysis/pipeline.py) (346). On the frontend, [Inbox.tsx](../web/src/pages/Inbox.tsx) (498) and [Settings.tsx](../web/src/pages/Settings.tsx) (283) are the pressure points.

### 3.2 Dependency shape

Imports are essentially acyclic by inspection:

```text
models ──► store ──► analysis ──► api
   ▲          ▲          ▲          ▲
   └── brightspace ──────┴──────────┘
   └── mail ─────────────┘
config ──► runtime ──► api / cli
```

The weak point is not cycle-freedom but **boundary discipline**: `api` is a closure over `store` and `runner`; `analysis` reaches through `store.conn`; transport concerns and domain logic share one factory.

---

## 4. What is genuinely well structured

### 4.1 Clear domain packages and small files

`brightspace/`, `analysis/` and `llm/` are recognisable domains. Naming is consistent. Most modules have a single job and a module docstring. There is no god file or framework maze.

### 4.2 Domain decisions are documented where they matter

This is the strongest part of the codebase:

- [store.py:1](../src/campus_assistant/store.py#L1) explains hashing, history, named changes and soft deletion.
- [pipeline.py:1](../src/campus_assistant/analysis/pipeline.py#L1) explains input-hash caching and retry-on-error.
- [runner.py:6](../src/campus_assistant/runner.py#L6) documents the Brightspace auth state machine.
- [session.py:1](../src/campus_assistant/brightspace/session.py#L1) explains persistent-profile and storage-state login behaviour.
- [classify.py:1](../src/campus_assistant/llm/classify.py#L1) documents neutral letter labels, prompt ordering, coverage and calibration caveats.
- [normalize.py:1](../src/campus_assistant/brightspace/normalize.py#L1) documents the `data`/`data.raw` split.

These comments are the best source for a behavioural spec.

### 4.3 Tests pin non-obvious semantics

The tests are small but targeted. They encode rules that are easy to break in a rewrite:

- Raw/meta differences are not changes; `data.submitted` changes are named.
- Deleted items are soft-deleted and restored, not recreated.
- Failed analysis attempts preserve the previous result while marking an error.
- Windowed calendar events must not be treated as removed.
- Classifier option keys are never shown to the model; permutations average letter bias.
- Brief file ranking prefers module anchors over filename matches.

These are more trustworthy than the prose documentation.

### 4.4 Operational documentation is strong

[README.md](../README.md) covers setup, systemd, data locations, auth flow, LLM providers, endpoints and UI. The systemd unit in [service.py:22](../src/campus_assistant/service.py#L22) is thoughtfully designed (cgroup containment, `TasksMax`, graphical-session binding). CI exists for backend tests, frontend build/test/lint.

### 4.5 Frontend foundations are reasonable

TanStack Query, typed UI primitives (`Card`, `Button`, `Badge`, `QueryState`), Tailwind and a small formatting layer. The UI is consistent in visual language and has no obvious state-management framework overkill.

### 4.6 Verified baseline health

- `npm run build` passes.
- `npm run lint` passes with one warning.
- `npm test` passes 12 tests.
- Backend coverage is 65.8%.

The caveat is that one backend test fails; see §5.1.

---

## 5. Findings

Severity reflects risk to the rewrite, not necessarily end-user impact today.

| ID | Severity | Finding | Evidence |
|---|---|---|---|
| F-01 | High | Triage filter contract mismatch; backend suite is red | [test_analysis.py:126](../tests/test_analysis.py#L126), [README.md:129](../README.md#L129), [api.py:165](../src/campus_assistant/api.py#L165) |
| F-02 | High | Settings “Fetch Models” calls GET against a POST-only endpoint | [client.ts:182](../web/src/api/client.ts#L182), [api.py:316](../src/campus_assistant/api.py#L316) |
| F-03 | High | Native clients read the wrong item fields | [campus_kde.py:440](../kde/app/campus_kde.py#L440), [main.qml:119](../kde/plasmoid/org.campus-assistant.widget/contents/ui/main.qml#L119) |
| F-04 | High | Core contract is implicit and duplicated across four representations | `ItemIn`/dict rows/TS interfaces/QML assumptions |
| F-05 | High | No response models, so OpenAPI does not describe responses | [api.py:76](../src/campus_assistant/api.py#L76) onward |
| F-06 | Medium | Configuration is read at import, instantiation and request time; mutable globals | [config.py:13](../src/campus_assistant/config.py#L13), [pipeline.py:36](../src/campus_assistant/analysis/pipeline.py#L36), [llm/__init__.py:70](../src/campus_assistant/llm/__init__.py#L70) |
| F-07 | Medium | Persistence abstraction leaks; no migrations | [pipeline.py:99](../src/campus_assistant/analysis/pipeline.py#L99), [evaluate.py:18](../src/campus_assistant/analysis/evaluate.py#L18), [store.py:20](../src/campus_assistant/store.py#L20) |
| F-08 | Medium | Shutdown does not cancel all tasks or close the store | [api.py:63](../src/campus_assistant/api.py#L63) |
| F-09 | Medium | Changelog/issue tracker contain “fixed” claims that are not implemented | [CHANGELOG.md:23](../CHANGELOG.md#L23), [.claude/issues/backend.md:28](../.claude/issues/backend.md#L28) |
| F-10 | Medium | Python type checking is configured but not installed or run in CI | [CONTRIBUTING.md:19](../CONTRIBUTING.md#L19), [pyproject.toml:33](../pyproject.toml#L33), [ci.yml](../.github/workflows/ci.yml) |
| F-11 | Medium | KDE/PySide6 surface is undeclared, unpackaged and untested | [campus_kde.py:25](../kde/app/campus_kde.py#L25), [kde_app.py:8](../src/campus_assistant/kde_app.py#L8), [pyproject.toml](../pyproject.toml) |
| F-12 | Low | History snapshot type mismatch between backend and TS | [store.py:372](../src/campus_assistant/store.py#L372), [types.ts:61](../web/src/api/types.ts#L61) |
| F-13 | Low | Docs and machine-specific paths are not reproducible | [.mcp.json:5](../.mcp.json#L5), [CLAUDE.md:1](../CLAUDE.md#L1), [personal-app.desktop:7](../kde/app/personal-app.desktop#L7) |
| F-14 | Low | Tracked files remain in ignored directories | `reports/`, `research_notes/` |

### 5.1 The data contract is implicit and already drifting

`ItemIn` is typed, but after ingestion almost everything is an untyped dict. `Store` returns raw SQLite rows; the API returns them directly; the frontend re-declares them by hand; QML and the tray app make their own assumptions. The `data` JSON has an undocumented schema (`raw`, `meta`, `from`, `submitted`, `module_path`, `type`, `attachments`, …) that multiple modules depend on.

Concrete failures:

**Triage filters are inconsistent and the backend test fails.**
[test_analysis.py:126](../tests/test_analysis.py#L126) and [README.md:129](../README.md#L129) use `?category=`, but [api.py:165](../src/campus_assistant/api.py#L165) accepts `categories`. The singular parameter is silently ignored. I verified that `?category=opportunity` returns every row; the integration test then fails at [test_analysis.py:132](../tests/test_analysis.py#L132) because the row it expected to be filtered in is not. Current result: **45 passed, 1 failed**. This also means one of the few API integration tests was giving false confidence.

**Settings “Fetch Models” is broken.**
[client.ts:182](../web/src/api/client.ts#L182) issues a default `GET`, while [api.py:316](../src/campus_assistant/api.py#L316) exposes `POST /settings/llm/models`. Verified response: **405 Method Not Allowed**.

**The native clients read fields from the wrong place.**
The API returns `title`, `due_at`, `course_name` at the item top level. The KDE tray reads `data.title` and `data.due_date` at [campus_kde.py:338](../kde/app/campus_kde.py#L338) and [campus_kde.py:440](../kde/app/campus_kde.py#L440). The QML widget reads `modelData.due_date` at [main.qml:119](../kde/plasmoid/org.campus-assistant.widget/contents/ui/main.qml#L119). Result: tray notifications show “Untitled”; the popup and widget show no due dates.

**History has a type mismatch.**
Backend decodes snapshots into objects at [store.py:372](../src/campus_assistant/store.py#L372), while [types.ts:61](../web/src/api/types.ts#L61) declares `snapshot: string`. The UI survives only because `safeParse` accepts both.

**Why this matters for the rewrite:** one contract, four representations, no executable link. Contract-first design and generated clients are the highest-leverage architectural change.

### 5.2 Configuration is ambient and partly global

There is a `Config` dataclass, but it is only one of several mechanisms:

- Env read at **instantiation** in [config.py:13](../src/campus_assistant/config.py#L13).
- Env read at **import time** for analysis caps/modes in [pipeline.py:36](../src/campus_assistant/analysis/pipeline.py#L36), prompts in [prompts.py:8](../src/campus_assistant/analysis/prompts.py#L8), and local LLM pause in [local.py:29](../src/campus_assistant/llm/local.py#L29).
- Env read at **request time** in [llm/__init__.py:57](../src/campus_assistant/llm/__init__.py#L57).
- Import-time env-file loading in [__init__.py:7](../src/campus_assistant/__init__.py#L7).
- Mutable process globals `PROVIDER_OVERRIDES` / `CUSTOM_PROVIDER_CONFIGS` in [llm/__init__.py:70](../src/campus_assistant/llm/__init__.py#L70), mirrored into SQLite by [api.py:66](../src/campus_assistant/api.py#L66).

Tests must monkeypatch module constants to change behaviour. A rewrite should load and validate settings once, inject them, and define precedence explicitly (defaults < env file < environment < runtime overrides).

### 5.3 The transport layer owns the application

[create_app](../src/campus_assistant/api.py#L49) is a 385-line factory containing every route, six Pydantic request models defined inside it (from [api.py:212](../src/campus_assistant/api.py#L212)), direct store calls, background-task spawning and static UI serving.

There are no routers, no application services, and **no `response_model`s**. FastAPI therefore documents inputs but not outputs. That is precisely why the TS/QML/KDE clients could drift.

### 5.4 Persistence is a SQLite script, not a repository

[store.py:20](../src/campus_assistant/store.py#L20) creates tables with `CREATE TABLE IF NOT EXISTS`; there is no schema version, migration path or `PRAGMA user_version`. `PRAGMA foreign_keys=ON` is set, but no foreign keys are declared. Rows are returned as dicts, so the DB shape is the API shape.

The change-tracking design itself is good and should be preserved:

- Hash only meaningful fields; exclude `raw` and `meta`.
- Keep previous versions in `item_history`.
- Log named field changes.
- Soft-delete items that disappear from a complete fetch; restore them if they reappear.

### 5.5 Lifecycle and error handling are incomplete

The lifespan at [api.py:63](../src/campus_assistant/api.py#L63) only cancels the scheduler. It does not cancel/await `runner.tasks` or the analysis task, and it never closes the store. The test run reports unclosed-database warnings.

Errors are captured in a **global in-memory deque** ([api.py:27](../src/campus_assistant/api.py#L27)) shared across app instances and lost on restart. Broad `except Exception` blocks are often deliberate at sync boundaries, but some are silent.

Subtle behavioural issue: [AnalysisRunner.request](../src/campus_assistant/runner.py#L158) drops the kwargs of a request that arrives during a run; the follow-up run uses the original arguments. This should be specified explicitly in the rewrite rather than inherited accidentally.

### 5.6 Three UI clients, no shared contract

React, the PySide6 tray app and the QML plasmoid all hand-roll HTTP and formatting. The PySide6 dependency is **not declared** in [pyproject.toml](../pyproject.toml), so `uv sync` does not install it. [kde_app.py:8](../src/campus_assistant/kde_app.py#L8) loads the app via an `importlib` path hack that only works in a source checkout. The plasmoid duplicates polling, formatting and state logic.

This is prototype scaffolding. A rewrite must decide explicitly: first-class supported surface, or dropped.

### 5.7 Documentation and “fixed” claims are not trustworthy

- [CHANGELOG.md:23](../CHANGELOG.md#L23) claims cookie storage moved to `keyring`; `keyring` is absent from code and dependencies.
- [CHANGELOG.md:29](../CHANGELOG.md#L29) claims sha256 sidecar cache invalidation; [documents.py:58](../src/campus_assistant/analysis/documents.py#L58) still uses mtime.
- [.claude/issues/backend.md:28](../.claude/issues/backend.md#L28) claims raw SQL moved into `Store.triage_items()` / `content_file_rows()` / `content_link_rows()`; those methods do not exist, and direct `store.conn` calls remain.
- [.env.example:1](../.env.example#L1) says “copy to `.env`”, but the loader reads `~/.config/campus-assistant/env`.
- `reports/` and `research_notes/` are in `.gitignore` yet remain tracked.
- Absolute machine paths appear in [.mcp.json:5](../.mcp.json#L5), [CLAUDE.md:1](../CLAUDE.md#L1) and [personal-app.desktop:7](../kde/app/personal-app.desktop#L7).

This matters for process: model-vetted specs and AI-generated issue trackers will confidently report “fixed” without code. Every claim must be tied to a diff, a test, or a CI run.

### 5.8 Quality gates are incomplete

- [CONTRIBUTING.md:19](../CONTRIBUTING.md#L19) says `uv run pyright`, but pyright is not a dev dependency in [pyproject.toml:33](../pyproject.toml#L33), is not installed in `.venv`, and is not run in [ci.yml](../.github/workflows/ci.yml).
- No Python linter/formatter is configured, despite `# noqa` comments suggesting ruff was intended.
- The backend suite is currently red; CI would fail on this checkout.
- Frontend tests cover only [format.test.ts](../web/src/components/format.test.ts) — no component, hook or integration tests, and no test of the most complex page, [Inbox.tsx](../web/src/pages/Inbox.tsx).
- Coverage is concentrated: store/normalize/pipeline are 84–98%, while `brightspace/client.py` is 26%, `brightspace/session.py` 17% and `llm/claude.py` 0%.

### 5.9 Smaller inconsistencies worth fixing in the rewrite

- **Taxonomy is stringly typed.** `source` and `kind` are free strings on `ItemIn`; the frontend hardcodes source/kind lists; normalisers produce seven Brightspace kinds and one mail kind.
- **`data` keys are a hidden schema.** Examples: `from`, `submitted`, `module_path`, `type`, `raw`, `meta`, `bulk`, `attachments`, `score_out_of`.
- **Time zone is hardcoded.** Prompts resolve dates in `Asia/Singapore`; naive datetimes are treated as UTC; no configuration.
- **Analysis cache invalidation is incomplete.** The triage hash includes item content and prompt version but not classifier model, mode or cutoffs, so changing those does not recompute results unless forced.
- **UI information architecture overlaps.** Sources, System and Settings all expose Brightspace/session/LLM state; Today/Inbox/Tasks/Browse overlap in message/task views.
- **Branding is inconsistent.** Repo `personal-app`, package `campus-assistant`, UI “Campus Assistant”, tray “Personal App”, sidebar header “Home”.
- **No auth.** Loopback binding reduces exposure, but any local page can still POST to state-changing endpoints. Treat this as an explicit security decision, not an omission.

---

## 6. What to preserve

These are the parts of the current design worth carrying into a rewrite, either as code or as executable acceptance criteria.

| Preserve | Why | Reference |
|---|---|---|
| Item identity `source:kind:external_id` | Stable across syncs; underpins change tracking, caching and labels | [models.py:36](../src/campus_assistant/models.py#L36) |
| Content hashing that ignores `raw`/`meta` | Prevents source bookkeeping from registering as user-visible changes | [store.py:104](../src/campus_assistant/store.py#L104) |
| History snapshots + soft delete/restore | Auditable and non-destructive | [store.py:151](../src/campus_assistant/store.py#L151) |
| Analysis input-hash caching | Makes re-runs cheap; avoids duplicate LLM calls | [pipeline.py:97](../src/campus_assistant/analysis/pipeline.py#L97) |
| Prompt versioning | Invalidates cached results when prompts change | [prompts.py:6](../src/campus_assistant/analysis/prompts.py#L6) |
| Rules → classifier → LLM cascade | Core product logic; supports local-only and calibrated modes | [pipeline.py:43](../src/campus_assistant/analysis/pipeline.py#L43) |
| Label-based evaluation | Turns user corrections into calibration data | [evaluate.py](../src/campus_assistant/analysis/evaluate.py) |
| Partial-fetch semantics | Windowed calendar results must not mark items missing | [sync.py:127](../src/campus_assistant/brightspace/sync.py#L127) |
| Pure Brightspace normalisers | Easily testable; encode Valence quirks | [normalize.py](../src/campus_assistant/brightspace/normalize.py) |
| Email identity and archive dedupe | Prevents duplicate mail across push/import paths | [mail.py:49](../src/campus_assistant/mail.py#L49) |
| File ranking heuristics | Encodes real course-layout knowledge | [pipeline.py:317](../src/campus_assistant/analysis/pipeline.py#L317) |
| Operational docs and systemd unit | Genuinely useful; hard-won details | [README.md](../README.md), [service.py:22](../src/campus_assistant/service.py#L22) |
| Targeted tests | Best behavioural specification available | [tests/](../tests) |

---

## 7. Rewrite strategy

### 7.1 Recommendation

Use a **strangler/parallel rebuild**:

1. Freeze behaviour with characterization tests against the current app.
2. Write the feature specification and acceptance criteria.
3. Write and vet the architecture specification.
4. Build the new core and contract alongside the old app.
5. Migrate a copy of real data and compare outputs.
6. Cut over, then delete the old surfaces.

Do not start by deleting the current implementation. It contains several non-obvious rules that are not yet written down.

### 7.2 Target architecture (tentative, to be vetted)

For a single-user local app, a **modular monolith** is the right shape. Avoid microservices, a frontend/backend split for its own sake, or a message broker.

Suggested boundaries:

```text
domain/          entities, value objects, invariants, pure rules
application/     use cases: sync, ingest, triage, brief, label, query
ports/           Repository, SourceAdapter, AnalysisProvider, EventSink, Clock
adapters/        sqlite, brightspace, mail/archive, claude, local-llm, filesystem
transport/       FastAPI routers, CLI commands
web/             generated client + presentational UI
```

Dependency rule: `domain` depends on nothing; `application` depends on `domain`/ports; adapters and transport depend inward.

### 7.3 Contract-first API

- Pydantic models for every request **and response**.
- `response_model` on every route.
- Generate `openapi.json` in CI and generate the TypeScript client/types from it.
- Add contract tests that fail when the committed OpenAPI document changes.
- If KDE/QML survives, consume the same schema or drop those clients.

This single change would have prevented F-01, F-02, F-03 and F-12.

### 7.4 Configuration and secrets

- One validated settings object, loaded once at startup.
- Explicit precedence: defaults < env file < environment < runtime overrides.
- Inject settings; no module-level `os.environ` reads.
- Validate provider names, ports, paths and URLs at startup.
- Treat secrets deliberately: env/keyring/file with 0600. Do not echo API keys in responses.

### 7.5 Persistence

- Repository interface; SQLite adapter behind it.
- Versioned migrations (`PRAGMA user_version` or Alembic).
- Foreign keys and check constraints where appropriate.
- Typed row mapping; no raw `sqlite3.Row` / dict rows across the boundary.
- Preserve item IDs and, if feasible, the analysis cache during migration.
- Provide export/import and backup instructions.

### 7.6 Lifecycle and observability

- Explicit startup/shutdown manager.
- Cancel and await all tasks; close the DB.
- Bounded background work; document coalescing semantics.
- Persisted event/error log or structured rotating logs instead of an in-memory deque.
- Health/readiness endpoints with meaningful checks.

### 7.7 Security and privacy

- Decide whether loopback-only is sufficient; otherwise add a local token/origin checks.
- CSRF-safe state-changing endpoints.
- Request size limits and ingest quotas.
- Clear disclosure of which content is sent to which LLM provider.
- No secrets in URLs or response bodies.

### 7.8 Frontend

- Generated API client; no hand-written response interfaces.
- Split pages into data hooks + presentational components.
- Consolidate overlapping pages (Sources/System/Settings; Today/Inbox/Tasks).
- Accessible primitives: keyboard activation for clickable rows, escape/ARIA for custom dropdowns.
- Component tests with Testing Library plus one end-to-end smoke test.

### 7.9 Quality gates

Make CI enforce:

- `ruff format --check` and `ruff check`
- `pyright`
- `pytest` with per-module coverage floors
- contract/OpenAPI diff
- `eslint`
- `tsc` / production build
- `vitest`
- one Playwright smoke test

A red suite should block merging. Warnings should be visible, not hidden in output.

---

## 8. Spec extraction checklist

Before rewriting, capture the following in feature specs. These are the rules that currently exist only in code, comments, prompts or tests.

### 8.1 Domain and ingestion

- Item identity, source/kind taxonomy, external IDs.
- The per-kind `data` schema and which keys are meaningful vs bookkeeping.
- Date/time normalisation, time zone, naive datetime handling.
- Email identity hash, MIME vs HTML fallback, archive newest-copy-wins.
- Brightspace normalisation for courses, assignments, quizzes, announcements, content, events, grades.

### 8.2 Change tracking

- Which fields are tracked.
- Why `raw` and `meta` are excluded.
- When a change is `created`, `updated`, `removed` or `restored`.
- When a fetch is “complete” and may mark items missing.
- Retention policy for history and changes.

### 8.3 Triage and briefs

- Rule precedence (self-mail, system senders).
- Classifier modes (`shadow`, `gate`, `trust`), cutoffs and coverage.
- When the LLM is skipped, deferred or retried.
- How labels override model output.
- What goes into the analysis input hash.
- Prompt versioning and cache invalidation.
- Brief candidate selection, submitted-task exclusion, file ranking, text budgets.
- Evaluation metrics and calibration reporting.

### 8.4 Sync and auth

- Auth states and transitions.
- Silent SSO refresh behaviour and timeouts.
- Per-host concurrency and profile locking.
- Pagination behaviour.
- Active-course heuristics and lookback windows.
- File download filters, size limits and cache invalidation.
- What happens when one endpoint fails.

### 8.5 API and UI

- Every endpoint, parameter name, status code and error shape.
- Filter and pagination semantics.
- Static UI serving and path traversal protection.
- Page flows, keyboard shortcuts, filters and empty/error states.
- Which surfaces are supported (web, KDE, plasmoid, CLI).

### 8.6 Operations

- Env vars, defaults and precedence.
- Data directories, permissions and backup.
- systemd behaviour and process lifecycle.
- Ports, bind address and health checks.
- Build/install/packaging story.

---

## 9. Open decisions

These should be decided in the architecture spec, not inherited accidentally.

1. **Supported surfaces:** web only, or web + KDE + plasmoid? If native clients stay, are they generated from the same contract?
2. **Auth model:** loopback trust, local token, Origin checks, or something else?
3. **Deployment model:** source checkout only, installed wheel, container, or AppImage?
4. **Multi-user/multi-institution:** remain single-user/Singapore-polytechnic-specific, or generalise hosts, time zones and sender rules?
5. **LLM privacy:** which tasks may use a remote provider by default? Is explicit consent required?
6. **Search:** keep SQL `LIKE`, or add SQLite FTS?
7. **History retention:** keep full snapshots forever, or compact after N versions?
8. **Classifier strategy:** keep logprob gate/trust, or replace with a trained decision model behind the same port?
9. **Notification model:** pull-only UI, desktop notifications, or both?
10. **Backward compatibility:** preserve existing item IDs and analysis cache, or accept a clean database?

Record each answer as an ADR and link it from the relevant feature spec.

---

## 10. Bottom line

The current code is a good prototype with unusually thoughtful domain comments and tests. It is not a good foundation for parallel feature growth because its contracts are implicit, its configuration is ambient, its transport owns the application, and its docs are not reliable.

A rewrite is feasible and likely worthwhile **if** it is specification-led:

- extract behaviour before replacing code;
- define the domain model and API contract first;
- generate clients from the contract;
- keep the good change-tracking and cascade logic;
- make CI enforce the quality gates the current repo only documents.

The feature-spec workspace starts at [specs/features/INDEX.md](../specs/features/INDEX.md). The architecture-spec placeholder is [specs/architecture/README.md](../specs/architecture/README.md).

---

## Appendix A — Evidence snapshot

Backend:

```text
45 passed, 1 failed
Coverage: 65.80% (required 60%)
Failing test: tests/test_analysis.py::test_triage_and_label_api
```

Frontend:

```text
npm test      -> 12 passed (format.ts only)
npm run lint  -> 0 errors, 1 warning (notify.tsx fast-refresh)
npm run build -> passed
```

API probes:

```text
GET /triage?category=opportunity     -> returns all rows (filter ignored)
GET /triage?categories=opportunity   -> returns only matching rows
GET /settings/llm/models             -> 405
POST /settings/llm/models            -> routed
```

## Appendix B — Documentation claims vs reality

| Claim | Reality |
|---|---|
| `CHANGELOG.md`: cookies migrated to `keyring` | No `keyring` dependency or usage; file storage remains |
| `CHANGELOG.md`: sha256 sidecar cache | mtime-based cache remains |
| `.claude/issues/backend.md`: raw SQL moved into Store methods | Direct `store.conn` calls remain; methods absent |
| `.env.example`: copy to `.env` | Loader uses `~/.config/campus-assistant/env` |
| `README.md`: `/triage?category=` | API accepts `categories` |
| `CONTRIBUTING.md`: `uv run pyright` | Pyright not installed or declared |

Treat all prose in this repository as untrusted until verified against code, tests or CI. That includes this document after the code changes.

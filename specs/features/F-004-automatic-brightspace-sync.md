# Brightspace sync and crawler integration

> **Specification state.** Accepted specification governing integration between `campus-assistant` and the standalone Brightspace Crawler daemon defined in [`F-019`](F-019-brightspace-crawler.md).
> Governs scheduling, item referencing, live query proxying, read-queue retry handling, and on-demand sync coordination.

| Field | Value |
|---|---|
| ID | F-004 |
| Status | Accepted |
| Owner | spiralsky |
| Created | 2026-10-25 |
| Last updated | 2026-10-28 |
| Target release | v1.0 |
| Related architecture | Standalone Crawler Service ([`F-019`](F-019-brightspace-crawler.md)), Local API Contract ([`F-015`](F-015-local-api-contract-security.md)) |
| Supersedes | — |
| Superseded by | — |

**Source key.** `owner` = confirmed by product owner; `baseline` = observed in current implementation; `proposal` = proposed integration details.

---

## 1. Summary

This specification governs how `campus-assistant` integrates with the standalone Brightspace Crawler daemon ([`F-019`](F-019-brightspace-crawler.md)). Instead of running browser automation and scraping directly in-process or duplicating raw course entities into its local SQLite database, `campus-assistant` treats the Brightspace Crawler service as the authoritative local source and query layer for academic data.

The crawler daemon independently manages its background sync schedule and local full-text search index, while `campus-assistant` coordinates with the daemon via its loopback HTTP REST API (`/v1`). `campus-assistant` exposes controls for users and downstream systems to trigger on-demand sync runs, inspect sync status, query Brightspace items and files on demand, and proxy mutations through the crawler's audited endpoints.

---

## 2. Problem and context

- **Monolithic coupling in baseline:** Previously, `campus-assistant` ran Playwright directly inside `brightspace/session.py` and `brightspace/sync.py`. A failure or crawl hang blocked background workers, duplicated scraping logic, and prevented other local tools or AI agents from inspecting courses without locking the SQLite database.
- **Data duplication & divergence:** Duplicating Brightspace entities into `personal-app`'s `items` table required complex multi-pass synchronization, custom file mirror management, and manual reconciliation of removed items.
- **Architectural separation:** With the standalone Brightspace Crawler defined in `F-019`, Brightspace data acquisition, session retention, blob deduplication, document text extraction, and FTS5 indexing are delegated to the crawler daemon. `campus-assistant` must consume this service cleanly over loopback HTTP without re-scraping or duplicating storage.

---

## 3. Users and jobs

| User / Consumer | Job / Need | Source |
|---|---|---|
| Student (User) | Trigger immediate Brightspace refresh from UI or CLI; inspect sync and auth health; browse academic items and files seamlessly alongside email tasks. | `owner` |
| Web UI / API clients | View course announcements, assignments, grades, and discussion threads without waiting on an active scraper. | `owner` |
| Triage & Planning Engine | Query deadlines and course briefs from the crawler on demand to feed study plans and upcoming task views. | `proposal` |
| System runner / CLI | Issue `campus sync` or click "Sync now" to dispatch a trigger to the crawler daemon and await progress. | `owner` |

---

## 4. Goals and non-goals

### Goals
- **G-1** `owner`: Decouple scraping and browser automation from `campus-assistant`; communicate exclusively via the crawler daemon's loopback REST API (`/v1`).
- **G-2** `owner`: Reference Brightspace items and file blobs on demand from the crawler rather than duplicating records into `campus-assistant`'s local store.
- **G-3** `owner`: The crawler daemon manages its own background cron schedule; `campus-assistant` exposes methods and endpoints to trigger on-demand synchronization runs.
- **G-4** `proposal`: Transparently expose crawler health, auth state (`ok`, `auth_required`), and active sync progress in `campus-assistant` UI and API.
- **G-5** `proposal`: Proxy user-initiated mutations (e.g. marking notifications read, checklist toggling, discussion posting) to the crawler's audited endpoints.

### Non-goals
- **NG-1** `owner`: Duplicating raw Brightspace items, discussion posts, or binary file blobs in `campus_assistant.db`.
- **NG-2** `proposal`: Managing Playwright browser instances or SSO MFA flows directly inside `campus-assistant` processes.
- **NG-3** `proposal`: Direct write access or raw table manipulation of the crawler's SQLite database (`crawler.db`).

---

## 5. Current behaviour (baseline)

- **Baseline flow:** `sync_brightspace()` launched headless Chromium via Playwright, authenticated against POLITEMall/SP LMS using saved cookies, walked course enrollment lists, called Valence REST endpoints, and inserted records directly into `campus-assistant`'s `items` table.
- **File handling:** Files were downloaded into `files/<host>/<course_id>/` and tracked via `store.record_file()`.
- **Overrides:** 
  - Direct Playwright scraping in `campus_assistant` is superseded by HTTP client calls to the crawler service.
  - The local store no longer persists Brightspace course/assignment/quiz items; queries for Brightspace data dynamically resolve or proxy to the crawler daemon.

---

## 6. Desired behaviour

### 6.1 Primary flow (On-demand sync trigger)
1. The user clicks "Sync Brightspace" in the web UI or runs `campus sync brightspace`.
2. `campus-assistant` issues `POST /v1/sync` to the crawler daemon's loopback URL (e.g. `http://127.0.0.1:8765/v1/sync`).
3. The crawler daemon accepts the request, returns `202 Accepted` with a `job_id`, and runs the sync job in the background.
4. `campus-assistant` polls `GET /v1/sync/{job_id}` or listens to server-sent progress events, surfacing progress percentage and surface milestones to the caller.
5. Upon completion, UI views refresh their queried items from the crawler.

### 6.2 Item query and display
1. When the user navigates to Today, Tasks, or Browse views, `campus-assistant` queries `GET /v1/items?kinds=assignment,quiz` from the crawler daemon.
2. The items are formatted into unified domain models (`ItemOut`) in-memory or blended with local email items for triage.
3. Content files and lecture slides are streamed or linked directly via the crawler's `/v1/files/{sha256}` endpoint.

### 6.3 Background schedule
1. The crawler daemon runs its internal cron scheduler (e.g. hourly or every 30 minutes).
2. `campus-assistant` does not need to maintain a timer to trigger crawler crawls; it periodically checks `GET /v1/status` to determine `last_crawled_at` and host health.

### 6.4 Failure and recovery
1. **Crawler daemon unreachable:** If the crawler process is down or starting up, read requests are queued with background retries (exponential backoff up to a timeout limit). The UI indicates a non-blocking syncing/reconnecting state while continuing to serve available local data. If the service remains unavailable after retries expire, `campus-assistant` reports status `unavailable` with an actionable prompt ("Brightspace crawler is not running. Start with `campus-crawler serve`").
2. **Authentication required:** If the crawler reports `auth_state: auth_required`, `campus-assistant` highlights a prompt to the user with a button or command to trigger `POST /api/v1/sources/brightspace/login`.

---

## 7. Functional rules

| ID | Rule | Source |
|---|---|---|
| **FR-1** | `campus-assistant` connects to the Brightspace crawler over HTTP REST at a configured loopback base URL (default: `http://127.0.0.1:8765`). | `proposal` |
| **FR-2** | `campus-assistant` shall not replicate or store Brightspace entities (announcements, content modules, assignments, quizzes, grades, discussions) in its own SQLite database. | `owner` |
| **FR-3** | `campus-assistant` queries Brightspace items dynamically from the crawler daemon on demand via `GET /v1/items`. | `owner` |
| **FR-4** | Scheduled automatic synchronization is managed internally by the crawler daemon; `campus-assistant` does not run independent scraping intervals for Brightspace. | `owner` |
| **FR-5** | `campus-assistant` exposes an on-demand sync interface (`POST /api/v1/sources/brightspace/sync` and CLI `campus sync brightspace`) that dispatches `POST /v1/sync` to the crawler and tracks job completion. | `owner` |
| **FR-6** | When document text or file streams are requested by personal-app views or LLM pipelines, requests are proxied directly to `/v1/files/{sha256}` and `/v1/files/{sha256}/text`. | `proposal` |
| **FR-7** | If the crawler returns `auth_state: auth_required`, `campus-assistant` sets its Brightspace integration status to `needs_auth` and presents the user with an interactive login action. | `proposal` |
| **FR-8** | Triage and task evaluations that create personal notes, triage labels, or review decisions store only the external reference (`item_id`) in `personal-app` tables without duplicating item payloads. | `proposal` |
| **FR-9** | Transient crawler unavailability triggers queued read retries with exponential backoff before failing with a non-blocking UI alert. | `owner` |

---

## 8. Data and contracts

### 8.1 API Surface (Exposed by `campus-assistant` under `/api/v1`)

To conform with [`F-015`](F-015-local-api-contract-security.md), all endpoints are grouped under `/api/v1/sources/brightspace/*`:

| Method | Path / Command | Request | Response | Errors |
|---|---|---|---|---|
| `GET` | `/api/v1/sources/brightspace/status` | — | `{ "healthy": bool, "auth_state": str, "last_synced_at": str, "active_courses": int }` | 503 if crawler unreachable after retries |
| `POST` | `/api/v1/sources/brightspace/sync` | `{ "mode": "incremental" \| "full" }` | `{ "job_id": str, "status": "running" }` | 409 if sync already in progress, 503 if unreachable |
| `GET` | `/api/v1/sources/brightspace/sync/{job_id}` | — | `{ "job_id": str, "status": "done" \| "running" \| "failed", "progress": float, "errors": [] }` | 404 if not found |
| `GET` | `/api/v1/sources/brightspace/courses` | `?active_only=true` | `list[CourseSummary]` | 503 if unreachable |
| `GET` | `/api/v1/sources/brightspace/items` | `?course_id=...&kind=...&limit=...` | Unified item feed proxied from crawler | 503 if unreachable |
| `POST` | `/api/v1/sources/brightspace/login` | `{ "host": str }` | `{ "status": "launched", "message": "Headed window opened" }` | 503 if unreachable |

### 8.2 Configuration

| Key | Default | Description |
|---|---|---|
| `crawler_api_url` | `http://127.0.0.1:8765` | Base URL of the standalone Brightspace crawler daemon |
| `crawler_timeout_sec` | `10` | HTTP request timeout for crawler status and metadata calls |

---

## 9. Edge cases and failure modes

| Case | Expected Behaviour |
|---|---|
| **Crawler daemon offline** | API returns 503 Service Unavailable with JSON code `crawler_unavailable`. UI displays an inline banner explaining the crawler service is not running. |
| **Crawler daemon restarting / busy** | Transient connection retries (max 2 retries, 500ms backoff). If still failing, return 503. |
| **Concurrent sync requests** | If a sync is already running on the crawler, `POST /api/brightspace/sync` returns HTTP 409 Conflict with the existing `job_id`. |
| **Auth expired / MFA prompt** | The crawler returns `auth_state: auth_required`. `campus-assistant` halts any pending on-demand fetch and prompts user to authenticate. |
| **Network drop during on-demand sync** | Crawler marks sync run as `failed` with error details; `campus-assistant` displays error to user without affecting cached data. |

---

## 10. Non-functional requirements

| Area | Requirement |
|---|---|
| **Performance** | Proxying items from the crawler loopback API shall add less than 20ms overhead. |
| **Privacy** | Communication stays strictly within loopback (`127.0.0.1`); no Brightspace tokens or course materials leave the local machine. |
| **Reliability** | An offline or crashing crawler daemon must never crash the main `campus-assistant` web server or API process. |
| **Observability** | Crawler connection errors and sync triggers are recorded in `campus-assistant` structured application logs. |

---

## 11. Compatibility and migration

- **Breaking:** Yes.
- **What changes:** Deprecates in-process Playwright browser scraping in `campus_assistant/brightspace/`. Removes table replication of Brightspace items from `store.py`.
- **Existing data:** Legacy Brightspace items in `campus_assistant.db` can be purged or marked archived. Triage notes and labels referencing Brightspace item IDs remain intact as foreign references.
- **Migration:** Run migration to drop or freeze legacy Brightspace sync tables; point configuration to local crawler endpoint.

---

## 12. Acceptance criteria

| ID | Given | When | Then | Test level |
|---|---|---|---|---|
| **AC-1** | The crawler daemon is running on port 8765 | A client calls `GET /api/brightspace/status` | It returns HTTP 200 with the crawler's auth state and health metrics (FR-1, FR-4) | integration |
| **AC-2** | The user requests an on-demand sync | The client calls `POST /api/brightspace/sync` | `campus-assistant` dispatches `POST /v1/sync` to the crawler and returns 202 with `job_id` (FR-5) | integration |
| **AC-3** | The crawler daemon is not running | A client calls `GET /api/brightspace/items` | It returns HTTP 503 with code `crawler_unavailable` and does not crash (FR-1) | unit |
| **AC-4** | Brightspace items are queried via `campus-assistant` | The items are fetched | They are retrieved from the crawler on demand and not written to `campus_assistant.db` (FR-2, FR-3) | integration |
| **AC-5** | The crawler enters `auth_required` state | A client polls `/api/brightspace/status` | The status returns `auth_state: auth_required` with an interactive login action available (FR-7) | integration |

---

## 13. Open questions and decisions

| ID | Question | Owner | Resolution | Date |
|---|---|---|---|---|
| **Q-1** | How should local triage labels and user notes associate with crawler items? | spiralsky | **Resolved**: Foreign item reference `item_id` preserved in triage tables without copying crawler payloads. | 2026-10-27 |
| **Q-2** | Should `campus-assistant` automatically spawn the crawler daemon if it is not running? | spiralsky | **Resolved**: Deferred / Optional. For v1, managed as an independent systemd/CLI service or started via supervisor. | 2026-10-27 |

---

## 14. Change log

| Date | Change | By |
|---|---|---|
| 2026-10-28 | Accepted specification: aligned REST routes with F-015 (`/api/v1/sources/brightspace/*`), added read request queuing with background retries, and promoted status from Draft to Accepted. | spiralsky & Assistant |
| 2026-10-27 | Authored full specification for Brightspace sync integrating with F-019 crawler daemon over REST API with on-demand referencing. | spiralsky & Assistant |
| 2026-10-25 | Reset to an empty owner-authored scaffold | Assistant |

# Brightspace crawler

> **Authoring state.** Owner-reviewed specification. Captures the architectural direction,
> L3 surface coverage, dual REST+MCP interface, safe mutation tiering, and storage model.
> Designed to serve as the blueprint for an independent, portable crawler service.

| Field | Value |
|---|---|
| ID | F-019 |
| Status | In review |
| Owner | spiralsky |
| Created | 2026-10-25 |
| Last updated | 2026-10-27 |
| Target release | v1.0 |
| Related architecture | Standalone service (portable submodule / independent package) |
| Supersedes | — |
| Superseded by | — |

**Source key.** `owner` = stated or confirmed by the owner; `baseline` = observed in the current implementation; `proposal` = agreed implementation details conforming to owner direction.

---

## 1. Summary

The Brightspace Crawler is a standalone, portable daemon and command-line interface that authenticates with one or more D2L Brightspace hosts, comprehensively crawls academic materials and student state at Depth Level 3 (catalogue, user state, bodies, and attachments), stores them in a durable local SQLite database with content-addressed file blobs, builds a full-text search index with document text extraction, and exposes this data through a versioned programmatic HTTP REST API and a native Model Context Protocol (MCP) server.

It is decoupled from `campus-assistant` so that scripts, background services, UI frontends, and AI coding/chat assistants can inspect courses, search discussion boards, download slides, monitor deadlines, and execute safe remote mutations (marking notifications as read, toggling checklists, and posting to discussion boards) without re-implementing scraping, session management, or rate limiting.

Brightspace remains the upstream system of record. Local modifications are audited, and sync reconciliation is non-destructive.

---

## 2. Problem and context

### 2.1 Baseline limitations
- Brightspace ingestion was previously tightly coupled inside `campus-assistant/brightspace/`, writing directly to a monolithic SQLite schema without a formal API boundary.
- Surface coverage was restricted to seven basic kinds, ignoring discussions, surveys, checklists, notification bell feeds, and full quiz attempt feedback.
- Files were only partially downloaded based on hardcoded extension whitelists, with no background text extraction for document search.
- AI tools and external scripts had no standardized, structured way (e.g. via MCP) to inspect course documents, announcements, or discussion posts.
- There was no structured capability to perform safe write actions (such as acknowledging alerts or posting forum replies) through a controlled audit trail.

### 2.2 Desired outcome
- An independent, portable codebase capable of living in its own repository or as a git submodule.
- Comprehensive L3 academic data capture across all active courses.
- Dual-interface delivery: HTTP REST on loopback for applications + MCP (stdio and SSE) for LLM agents.
- Searchable local cache with FTS5 indexing and background text extraction for PDF, DOCX, and PPTX files.
- Safe, tiered read-write operations backed by an append-only audit log.

---

## 3. Users and jobs

| User / Consumer | Job / Need | Source |
|---|---|---|
| Student (Owner) | Query deadlines, search lecture slides, read discussion forums, and track notifications without opening a web browser. | `owner` |
| AI Assistants (MCP Clients) | Contextualize queries with course content, find specific assignment requirements, extract text from slides, and draft/post discussion replies. | `owner` |
| `campus-assistant` | Consume structured Brightspace events and items via HTTP rather than managing browser automation and raw JSON normalisation. | `proposal` |
| Automation Scripts / CLI | Run scheduled sync jobs, query status, trigger interactive login, and export data. | `proposal` |

---

## 4. Goals and non-goals

### Goals
- **G-1** `owner`: Standalone, portable program with an independent lifecycle, CLI, and programmatic API.
- **G-2** `owner`: Comprehensive L3 academic surface coverage: Courses, Announcements, Content/Files, Assignments, Quizzes, Grades, Calendar, Notification Bell/Alerts, Discussions (forums/topics/threads/posts), Surveys, and Checklists.
- **G-3** `owner`: Native Model Context Protocol (MCP) server support (both stdio and SSE transport) for AI agent integration.
- **G-4** `owner`: Local full-text indexing (SQLite FTS5) with automated text extraction from downloaded documents (PDF, DOCX, PPTX).
- **G-5** `owner`: Safe, permissioned read-write capabilities for v1 (marking alerts read, updating post read-state, checklist toggling, discussion posting) with strict audit logging.
- **G-6** `owner`: Content-addressed, deduplicated blob storage preserving original binary files.
- **G-7** `owner`: Configurable, optional version history (disabled by default; metadata snapshots when enabled).

### Non-goals
- **NG-1** `owner`: Assignment submission uploads and quiz-taking in v1 (deferred to v2).
- **NG-2** `proposal`: Bypassing institutional authentication or MFA mechanisms.
- **NG-3** `proposal`: Scraping third-party LTI / external tools (e.g. Panopto, Zoom, Turnitin, Pearson/Wiley external portals).
- **NG-4** `proposal`: Multi-tenant or multi-user server hosting; designed as a single-user local daemon.
- **NG-5** `proposal`: Full-blown web UI (provided by external clients such as `personal-app` web).

---

## 5. System architecture & deployment

### 5.1 Project structure and packaging
The crawler is engineered as a standalone package (`campus-crawler` or `brightspace-crawler`) with its own:
- `pyproject.toml` with pinned dependencies (Playwright, FastAPI, Uvicorn, SQLite/aiosqlite, Pydantic v2, PyPDF, python-docx, python-pptx, mcp).
- Independent virtual environment and lockfile.
- CLI entrypoints:
  - `campus-crawler serve`: Runs the FastAPI HTTP daemon and SSE MCP endpoint.
  - `campus-crawler mcp`: Runs the stdio MCP server for direct editor/agent integration.
  - `campus-crawler auth login`: Launches interactive headed browser for SSO/MFA authentication.
  - `campus-crawler sync`: Triggers an on-demand sync job via CLI or IPC.
  - `campus-crawler search`: Fast CLI search over indexed items and extracted documents.

### 5.2 Filesystem layout
```text
~/.local/share/campus-crawler/          # Configurable via CRAWLER_DATA_DIR
  ├── config.json                       # Crawler settings, host list, retention policies
  ├── crawler.db                        # SQLite database (WAL mode): relational entities & FTS5
  ├── blobs/                            # Content-addressed binary store
  │   └── sha256/
  │       └── ab/
  │           └── cd/
  │               └── <full-sha256>     # Original unmodified binary files
  ├── session/
  │   └── <host-slug>/                  # Playwright persistent context, cookies, local storage
  └── logs/
      └── crawler.log                   # Structured rotating logs with redacted secrets
```

---

## 6. Functional rules

### General operation & boundaries
- **FR-1** `owner`: The crawler runs as an independent daemon and CLI, completely decoupled from the main application lifecycle.
- **FR-2** `owner`: It exposes a versioned loopback HTTP REST API (`/v1`) and a native MCP server (`stdio` and `SSE`).
- **FR-3** `owner`: The crawler supports multi-host Brightspace configurations under a single local user profile.

### Surface coverage & depth (L3)
- **FR-4** `owner`: The crawler retrieves the following surfaces in v1:
  - **Courses & Enrollments**: Active and pinned offerings, metadata, codes, start/end dates.
  - **Announcements**: Full HTML body, sanitised text, author, attachments, pin status.
  - **Content Tree & Files**: Modules, topic hierarchy, HTML topic bodies, downloaded documents, external URLs.
  - **Assignments**: Descriptions, instructions, rubric criteria, due dates, student submission history, scores, feedback text, and feedback attachments.
  - **Quizzes**: Metadata, availability windows, time limits, attempt limits, historical attempts taken, scores, and feedback.
  - **Grades**: Gradebook structure, point/weight values, letter grades, instructor comments.
  - **Calendar**: Events, schedule entries, assignment/quiz deadlines within a rolling window (`-30` days past, `+180` days future).
  - **Notifications / Alerts**: Minibar alert feed (subscriptions, updates, grade alerts) and unread counts.
  - **Discussions**: Forums, topics, threads, and individual posts, including author metadata, post dates, bodies, attachments, and read states.
  - **Surveys**: Survey metadata, descriptions, active dates, and student completion status.
  - **Checklists**: Checklists, item titles, descriptions, due dates, and completion status.

### Storage & full-text indexing
- **FR-5** `owner`: Original files are saved unmodified in content-addressed storage keyed by SHA-256. Identical files across courses share a single physical blob.
- **FR-6** `owner`: Text extraction runs asynchronously on supported downloaded formats (PDF, DOCX, PPTX, HTML, plain text). Extracted text is stored in `file_extractions` and indexed in SQLite FTS5.
- **FR-7** `proposal`: SQLite database runs in WAL mode with foreign keys enabled (`PRAGMA foreign_keys = ON; PRAGMA journal_mode = WAL;`).

### Mutations & write actions (Tiers 1 & 2)
- **FR-8** `owner`: The crawler supports safe v1 write operations:
  - Marking notification alerts as read/dismissed (`POST /v1/notifications/{id}/read`).
  - Marking discussion posts/threads as read (`POST /v1/discussions/posts/{id}/read`).
  - Toggling checklist items (`POST /v1/checklists/items/{id}/toggle`).
  - Creating discussion replies or threads (`POST /v1/discussions/topics/{id}/posts`).
- **FR-9** `owner`: Assignment submission uploads and quiz submissions are strictly excluded from v1 mutations.
- **FR-10** `owner`: Every mutation must record an immutable row in the `audit_log` table containing timestamp, initiator identity (e.g. `rest:client`, `mcp:tool`), target endpoint, payload parameters, and upstream response status.
- **FR-11** `proposal`: Mutating requests against Brightspace must automatically extract, supply, and validate required CSRF tokens (`d2l_referrer`, `X-Csrf-Token`).

### History & retention
- **FR-12** `owner`: History is optional and governed by `history.enabled` (default: `false`).
- **FR-13** `proposal`: When history is disabled, the crawler maintains current state, `last_seen`, and soft-deletion markers; no version rows are written. History query endpoints return `{"enabled": false, "versions": []}`.
- **FR-14** `proposal`: When history is enabled, it records metadata snapshots and named changed fields. File blob versioning remains off by default to conserve disk space.
- **FR-15** `proposal`: Unreferenced blobs (orphans resulting from content replacement) are purged after a 14-day grace period.

### Sync reconciliation & failure isolation
- **FR-16** `proposal`: A failure in one surface or course (e.g. HTTP 403 Forbidden on a disabled tool) records a surface error and does not abort the crawl of other surfaces or courses.
- **FR-17** `proposal`: Soft-deletion occurs only after a complete, successful fetch of an entire surface. Windowed surfaces (calendar, alerts) never mark missing items as deleted.
- **FR-18** `proposal`: Mid-crawl interruptions or network drops leave existing cache records intact and mark the sync run as `partial` or `failed`.

---

## 7. Authentication and session lifecycle

### 7.1 States
- `ok`: Session cookies and CSRF tokens are valid; `whoami` check succeeds.
- `checking`: Actively validating session with Brightspace.
- `refreshing`: Performing background headless SSO refresh.
- `auth_required`: Session expired or MFA challenged; interactive login required.
- `error`: Network or infrastructure error reaching the authentication authority.

### 7.2 Headless & background refresh
1. Before every scheduled or requested crawl, the crawler checks `GET /d2l/api/lp/{lp}/users/whoami`.
2. If the check returns 401 or redirects to an SSO landing page:
   - The crawler launches a headless Playwright context using the saved persistent profile.
   - It navigates to the host root URL, waiting up to 15 seconds to detect whether the institutional IdP session automatically issues fresh cookies.
   - If fresh session cookies are acquired, they are saved, and the state returns to `ok`.
3. If headless navigation stops on an interactive password, SMS, or authenticator prompt:
   - The state transitions to `auth_required`.
   - The crawler writes a diagnostic event and halts the crawl without touching existing cached records.

### 7.3 Interactive login protocol
1. When in `auth_required`, the user or client initiates login:
   - **CLI**: `campus-crawler auth login --host <host>` spawns a visible (headed) Chromium window using the profile.
   - **REST API**: `POST /v1/auth/login` launches the headed window on the desktop session and streams progress via SSE.
2. The user interacts directly with the institution's SSO and MFA screens.
3. The crawler observes URL changes and network traffic until it detects a successful redirect to the Brightspace home page (`/d2l/home`) and receives valid session cookies.
4. The crawler captures session cookies and CSRF tokens, closes the headed browser window, persists the storage state to disk, updates status to `ok`, and notifies active listeners.

---

## 8. Data model and schema

### 8.1 SQLite relational schema (highlights)

#### `hosts`
- `id` (TEXT PRIMARY KEY): Hostname (e.g. `splms.polite.edu.sg`).
- `label` (TEXT): Display name.
- `auth_state` (TEXT): `ok`, `checking`, `refreshing`, `auth_required`, `error`.
- `last_checked_at` (TEXT UTC ISO8601).

#### `courses`
- `id` (TEXT PRIMARY KEY): Format `{host}:course:{org_unit_id}`.
- `host` (TEXT NOT NULL REFERENCES hosts(id)).
- `org_unit_id` (TEXT NOT NULL).
- `name` (TEXT NOT NULL), `code` (TEXT).
- `starts_at` (TEXT), `ends_at` (TEXT).
- `is_active` (INTEGER NOT NULL DEFAULT 1).
- `last_crawled_at` (TEXT).

#### `items`
- `id` (TEXT PRIMARY KEY): Format `{host}:{kind}:{course_ou}:{external_id}`.
- `host` (TEXT NOT NULL), `course_id` (TEXT REFERENCES courses(id)).
- `kind` (TEXT NOT NULL): `announcement`, `content_topic`, `content_module`, `assignment`, `quiz`, `grade`, `calendar_event`, `alert`, `survey`, `checklist`.
- `external_id` (TEXT NOT NULL).
- `title` (TEXT NOT NULL).
- `body_html` (TEXT), `body_text` (TEXT).
- `url` (TEXT).
- `starts_at` (TEXT), `due_at` (TEXT), `ends_at` (TEXT), `occurred_at` (TEXT).
- `data` (TEXT JSON NOT NULL): Normalized kind-specific attributes.
- `raw` (TEXT JSON): Raw upstream payload (omitted from change hash).
- `content_hash` (TEXT NOT NULL): SHA-256 hash of normalized user-visible fields.
- `first_seen` (TEXT NOT NULL), `last_seen` (TEXT NOT NULL), `deleted_at` (TEXT).

#### `discussions`
- `id` (TEXT PRIMARY KEY): `{host}:post:{post_id}`.
- `course_id` (TEXT NOT NULL REFERENCES courses(id)).
- `forum_id` (TEXT NOT NULL), `topic_id` (TEXT NOT NULL), `thread_id` (TEXT).
- `parent_post_id` (TEXT).
- `title` (TEXT NOT NULL), `body_html` (TEXT), `body_text` (TEXT).
- `author_name` (TEXT), `posted_at` (TEXT NOT NULL).
- `is_read` (INTEGER NOT NULL DEFAULT 0).
- `content_hash` (TEXT NOT NULL).

#### `checklists` & `checklist_items`
- `id` (TEXT PRIMARY KEY): `{host}:checklist_item:{item_id}`.
- `checklist_id` (TEXT NOT NULL), `course_id` (TEXT NOT NULL).
- `title` (TEXT NOT NULL), `description` (TEXT), `due_at` (TEXT).
- `is_checked` (INTEGER NOT NULL DEFAULT 0).

#### `blobs`
- `sha256` (TEXT PRIMARY KEY): SHA-256 hex hash.
- `byte_size` (INTEGER NOT NULL).
- `content_type` (TEXT NOT NULL).
- `first_seen` (TEXT NOT NULL), `last_seen` (TEXT NOT NULL).

#### `file_refs`
- `id` (TEXT PRIMARY KEY): UUID.
- `item_id` (TEXT NOT NULL REFERENCES items(id)).
- `blob_sha256` (TEXT NOT NULL REFERENCES blobs(sha256)).
- `role` (TEXT NOT NULL): `content_document`, `assignment_instruction`, `submission_attachment`, `feedback_attachment`, `discussion_attachment`, `embedded_image`.
- `filename` (TEXT NOT NULL).
- `origin_url` (TEXT NOT NULL).
- `ordinal` (INTEGER DEFAULT 0).

#### `file_extractions`
- `blob_sha256` (TEXT PRIMARY KEY REFERENCES blobs(sha256)).
- `extracted_text` (TEXT NOT NULL).
- `extractor_version` (TEXT NOT NULL).
- `extracted_at` (TEXT NOT NULL).

#### `audit_log`
- `id` (INTEGER PRIMARY KEY AUTOINCREMENT).
- `timestamp` (TEXT NOT NULL).
- `actor` (TEXT NOT NULL): `rest:client_name` or `mcp:tool_name`.
- `action` (TEXT NOT NULL): e.g. `notification.mark_read`, `discussion.post`.
- `target_id` (TEXT NOT NULL).
- `payload` (TEXT JSON).
- `upstream_status` (INTEGER).
- `success` (INTEGER NOT NULL).

#### FTS5 Index (`fts_search`)
Virtual table indexing `items`, `discussions`, and `file_extractions`:
```sql
CREATE VIRTUAL TABLE fts_search USING fts5(
    entity_id UNINDEXED,
    course_id UNINDEXED,
    kind UNINDEXED,
    title,
    body,
    content=' '
);
```

---

## 9. API and MCP contracts

### 9.1 REST API specification (`/v1`)

| Method | Path | Summary / Description |
|---|---|---|
| `GET` | `/v1/health` | Liveness/readiness, database health, disk storage stats. |
| `GET` | `/v1/status` | Current sync state, last run results, host auth states, history settings. |
| `GET` | `/v1/auth` | List configured hosts, current users, and auth status. |
| `POST` | `/v1/auth/login` | Initiate login for host; returns job ID or streams SSE. |
| `POST` | `/v1/sync` | Trigger sync. Body: `{ "hosts"?: [], "courses"?: [], "mode": "incremental" \| "full" }`. Returns `202 Accepted` with `job_id`. |
| `GET` | `/v1/sync/{job_id}` | Poll progress, surface counts, and errors of a sync run. |
| `GET` | `/v1/courses` | List courses. Query: `host`, `active_only`. |
| `GET` | `/v1/items` | Unified item feed. Query: `course_id`, `kind`, `since`, `cursor`, `limit`. |
| `GET` | `/v1/items/{id}` | Detailed item record, linked file references, and metadata. |
| `GET` | `/v1/discussions` | List discussion forums, topics, and thread summaries. |
| `GET` | `/v1/discussions/topics/{id}/posts` | Get threaded posts under a topic. |
| `GET` | `/v1/files/{sha256}` | Stream binary file with original `Content-Type` and safe disposition header. |
| `GET` | `/v1/files/{sha256}/text` | Get extracted plain text for a document. |
| `GET` | `/v1/search` | Full-text search across titles, bodies, and extracted document text. |
| `POST` | `/v1/notifications/{id}/read` | **Mutation (Tier 1)**: Mark an alert as read. |
| `POST` | `/v1/discussions/posts/{id}/read` | **Mutation (Tier 1)**: Mark a discussion post as read. |
| `POST` | `/v1/checklists/items/{id}/toggle` | **Mutation (Tier 1)**: Toggle checklist completion status. |
| `POST` | `/v1/discussions/topics/{id}/posts` | **Mutation (Tier 2)**: Create a new post or reply. Body: `{ "thread_id"?: str, "body_html": str }`. |
| `GET` | `/v1/audit` | Query immutable audit log records. |

### 9.2 MCP (Model Context Protocol) tool declarations

When invoked via `campus-crawler mcp` or connected via `/mcp/sse`, the daemon registers the following MCP tools:

1. **`brightspace_search`**
   - *Description*: Search through announcements, content slides, assignment prompts, and discussion posts.
   - *Parameters*: `query` (str), `course_id` (optional str), `kinds` (optional list[str]), `limit` (default: 10).
2. **`brightspace_get_upcoming`**
   - *Description*: Retrieve upcoming quizzes, assignments, and calendar deadlines.
   - *Parameters*: `days_ahead` (default: 14), `course_id` (optional str).
3. **`brightspace_list_courses`**
   - *Description*: List active courses, offering codes, and semester bounds.
4. **`brightspace_get_course_outline`**
   - *Description*: Retrieve the hierarchical content module tree for a specific course.
   - *Parameters*: `course_id` (str).
5. **`brightspace_read_document_text`**
   - *Description*: Retrieve extracted text from a course lecture slide, reading, or syllabus file.
   - *Parameters*: `blob_sha256` (str).
6. **`brightspace_get_discussion_thread`**
   - *Description*: Read full conversation thread under a discussion topic.
   - *Parameters*: `topic_id` (str), `thread_id` (str).
7. **`brightspace_list_alerts`**
   - *Description*: Inspect minibar bell notifications and update alerts.
   - *Parameters*: `unread_only` (bool, default: true).
8. **`brightspace_mark_alert_read`**
   - *Description*: Mark a notification alert as read/acknowledged.
   - *Parameters*: `alert_id` (str).
9. **`brightspace_post_discussion_reply`**
   - *Description*: Post a message or reply into a course discussion board.
   - *Parameters*: `topic_id` (str), `thread_id` (optional str), `content_html` (str).

---

## 10. Edge cases, failure modes, and recovery

| Hazard / Scenario | Expected Behaviour |
|---|---|
| **Interrupted File Download** | Download writes to `.tmp.<uuid>`. File is checked for size and SHA-256 before being atomically moved into `blobs/`. Interrupted downloads leave zero corrupted blobs. |
| **Tool Disabled in Course (403/404)** | Records an entry in `sync_run.errors` for that surface; existing items for that tool are preserved and never marked deleted. |
| **Rate Limiting (429 / 503)** | Exponential backoff (initial 2s, factor 2, jitter ±20%, max 3 retries). Crawl continues if downstream requests recover. |
| **SSO Session Expiry Mid-Crawl** | Surface fails with `auth_required`. Active crawl halts cleanly, saving all items ingested up to that point. No data is purged. |
| **Discussion Post Mutation Fails CSRF** | Refresh CSRF token from active session context; retry once. If still failing, write failure to `audit_log` and return 403 with code `csrf_invalid`. |
| **Large File Exceeds Limit** | Files over `max_file_size_mb` (default: 100 MB) are skipped; a placeholder `FileRef` is created with `skipped: true` and size recorded. |
| **Unsupported File Text Extraction** | Extractor logs a warning and marks `file_extractions` with `status: unsupported`. Original file remains fully downloadable. |
| **Database Locked (Busy)** | WAL mode prevents reader contention. Writers use a 10-second busy timeout. |

---

## 11. Acceptance criteria

### Core service & architecture
- **AC-1** (integration): The crawler starts independently without `campus-assistant`, creates its database and directories, and responds to `GET /v1/health` with `status: ok`.
- **AC-2** (integration): The crawler exposes an MCP server over stdio (`campus-crawler mcp`) that responds to `tools/list` with all registered tools.

### Surface coverage & ingestion
- **AC-3** (integration): Given a valid Brightspace session, crawling an active course successfully extracts:
  - Course metadata and announcements with rich text.
  - Content module tree and downloadable document blobs.
  - Assignments with descriptions, due dates, student submission history, and grades.
  - Quizzes with start/due/end dates and student attempt history.
  - Discussion forums, topics, and threaded posts with read flags.
  - Surveys and checklists with completion statuses.
  - Notification alerts with category and unread status.

### File storage & text extraction
- **AC-4** (unit/integration): Downloading a duplicate file across two different courses creates two `file_refs` pointing to exactly one physical blob on disk.
- **AC-5** (integration): Uploading a PDF/DOCX lecture slide triggers background text extraction; query via `GET /v1/search?q=...` returns the matching document.

### Authentication & refresh
- **AC-6** (integration): When session cookies expire, a request to sync triggers a silent headless SSO check; if MFA is required, the status cleanly transitions to `auth_required` without crashing.
- **AC-7** (manual/integration): Invoking `campus-crawler auth login` opens a headed browser, captures credentials upon successful login, and updates daemon status to `ok`.

### Mutations & audit trail
- **AC-8** (integration): Calling `POST /v1/notifications/{id}/read` marks the alert as read upstream, updates the local cached row, and writes an entry into `audit_log`.
- **AC-9** (integration): Calling `POST /v1/discussions/topics/{id}/posts` creates a post in Brightspace, updates the local discussion cache, and logs the action in `audit_log`.
- **AC-10** (unit): Calling an assignment submission endpoint returns `501 Not Implemented` with code `mutation_out_of_scope_v1`.

---

## 12. Resolved decisions

| ID | Topic | Resolution |
|---|---|---|
| **Q-1** | Surface Menu & Depth | **Resolved**: L3 depth across all academic surfaces: Courses, Announcements, Content/Files, Assignments, Quizzes, Grades, Calendar, Notification Bell, Discussions, Surveys, and Checklists. |
| **Q-2** | Storage Layout | **Resolved**: SQLite (WAL) for metadata/FTS5 + content-addressed directory (`blobs/sha256/xx/yy/<hash>`). |
| **Q-3** | Auth Mechanism | **Resolved**: Playwright persistent profile; background silent refresh; headed CLI/API login on `auth_required`. |
| **Q-4** | Deployment Boundary | **Resolved**: Portable independent project (submodule or standalone package) with CLI and background daemon. |
| **Q-5** | Interfaces | **Resolved**: Loopback HTTP REST API (`/v1`) + Native Model Context Protocol (MCP) server. |
| **Q-6** | Document Search | **Resolved**: Automated background text extraction (PDF, DOCX, PPTX) into SQLite FTS5. |
| **Q-7** | Mutation Scope | **Resolved**: v1 includes non-destructive state changes (read flags, checklists) and discussion posting. Assignment submissions deferred to v2. All writes logged to `audit_log`. |
| **Q-8** | History Setting | **Resolved**: Optional; disabled by default. When enabled, records metadata snapshots; file versions stay off by default. |

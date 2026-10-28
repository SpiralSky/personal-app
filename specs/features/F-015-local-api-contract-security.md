# Local API contract and security

> **Specification state.** Draft establishing the versioned REST API contract (`/api/v1`), standard response/error envelope, schema generation, loopback security, and CORS/Origin restrictions for `campus-assistant`.

| Field | Value |
|---|---|
| ID | F-015 |
| Status | Draft |
| Owner | spiralsky |
| Created | 2026-10-27 |
| Last updated | 2026-10-27 |
| Target release | v1.0 |
| Related architecture | Canonical Item Taxonomy ([`F-002`](F-002-canonical-item-taxonomy.md)), Crawler Integration ([`F-004`](F-004-automatic-brightspace-sync.md)), Email Ingestion ([`F-005`](F-005-email-ingestion.md)) |
| Supersedes | — |
| Superseded by | — |

**Source key.** `owner` = confirmed by product owner; `baseline` = observed in current implementation; `proposal` = proposed specification.

---

## 1. Summary

This specification defines the local programmatic HTTP REST API for `campus-assistant`. It establishes a stable, versioned contract (`/api/v1`) serving all frontend and client consumers (the React Web UI, CLI commands, KDE Plasma widgets, and external scripts).

Because `campus-assistant` runs as a single-user local daemon handling sensitive academic materials and personal emails without cloud authentication, security is enforced through strict transport isolation: binding exclusively to loopback interfaces (`127.0.0.1` / `::1`), strict Cross-Origin Resource Sharing (CORS) rules rejecting untrusted browser origins, Host-header validation preventing DNS rebinding attacks, and standardized error and pagination envelopes.

---

## 2. Problem and context

- **API drift & unversioned endpoints:** In the baseline implementation, endpoints (`/items`, `/triage`, `/upcoming`, `/changes`, `/ingest`) were mounted directly at the root without API versioning. When internal response shapes changed, external clients (KDE widget, web app) experienced silent breakage or field mismatches.
- **Inconsistent error formats:** Some endpoints returned standard FastAPI/Starlette detail dictionaries (`{"detail": "Not found"}`), others returned string messages, and some returned HTTP 200 with inline error arrays (`"errors": [...]`). A consistent error envelope is required for robust client error handling.
- **Local security & DNS rebinding risks:** A local HTTP server without authentication is vulnerable to malicious websites executing drive-by cross-origin requests (`fetch('http://127.0.0.1:8000/items')`) or DNS rebinding. Without Origin checks and Host header validation, a browser tab visiting an external site could exfiltrate emails, Brightspace assignments, or trigger LLM tasks.
- **Contract-first client generation:** The React frontend and future desktop integration should consume auto-generated TypeScript clients derived from an authoritative OpenAPI schema.

---

## 3. Users and jobs

| User / Consumer | Job / Need | Source |
|---|---|---|
| Web Frontend (`web/`) | Query items, triage queues, task briefs, and trigger sync jobs using a typed API client. | `owner` |
| CLI (`campus`) | Execute daemon status queries, manual sync triggers, and data imports via loopback REST. | `owner` |
| KDE Desktop Integration | Display badge counts of unread emails and upcoming deadlines via a low-overhead status endpoint. | `proposal` |
| External Tools / AI Agents | Inspect courses and tasks programmatically without database locking. | `owner` |

---

## 4. Goals and non-goals

### Goals
- **G-1** `owner`: Versioned API surface mounted at `/api/v1`, preserving `/calendar.ics` and legacy endpoints for a migration period.
- **G-2** `owner`: Strict local loopback binding (`127.0.0.1` and `::1`); refuse public network interface exposure by default.
- **G-3** `proposal`: Strong Origin and Host header validation to prevent Cross-Site Request Forgery (CSRF) and DNS rebinding attacks.
- **G-4** `proposal`: Standardized JSON envelopes for pagination and errors with machine-readable error codes.
- **G-5** `proposal`: Deterministic OpenAPI 3.1 specification generation for automated TypeScript client compilation.

### Non-goals
- **NG-1** `owner`: Implementing complex multi-user role-based access control (RBAC) or cloud OAuth2 authentication; `campus-assistant` is fundamentally a single-user local tool.
- **NG-2** `proposal`: Exposing WebSocket streaming; Server-Sent Events (SSE) or short polling are used for progress updates.

---

## 5. Current behaviour (baseline)

- **Endpoints:** Unversioned (`/health`, `/status`, `/ingest`, `/ingest/email`, `/items`, `/items/{id}`, `/upcoming`, `/changes`, `/calendar.ics`, `/triage`, `/tasks`, `/settings`).
- **Security:** Bound to `127.0.0.1:8000` by default. No Origin checking or Host header verification is enforced.
- **Error format:** FastAPI default `{"detail": "..."}` or custom JSON responses.
- **Static files:** Serves frontend build files from `web/dist` directly at root `/`.

---

## 6. Desired behaviour

### 6.1 Versioning and URL Hierarchy
- Canonical API endpoints are mounted under `/api/v1/`.
- Non-API routes:
  - `/calendar.ics`: iCalendar export for calendar apps.
  - `/`: Static single-page application (SPA) frontend.
  - `/api/openapi.json`: Authoritative OpenAPI schema.

### 6.2 Standard Response & Pagination Envelope
All collection endpoints (`/api/v1/items`, `/api/v1/changes`, etc.) return a consistent envelope:

```json
{
  "data": [ ... ],
  "meta": {
    "total": 142,
    "limit": 50,
    "offset": 0,
    "has_more": true
  }
}
```

### 6.3 Standard Error Envelope
Errors return standard HTTP status codes (4xx, 5xx) with a predictable JSON envelope:

```json
{
  "error": {
    "code": "item_not_found",
    "message": "Item 'email:school:123' does not exist.",
    "details": {},
    "timestamp": "2026-10-27T16:25:00Z"
  }
}
```

### 6.4 Security Architecture
1. **Loopback Only:** Default listen address is strictly `127.0.0.1`. Binding to `0.0.0.0` requires explicit configuration flag `--allow-remote` with a warning.
2. **Origin Validation:**
   - Any request carrying an `Origin` header from a foreign browser tab (e.g. `Origin: http://evil.com`) is rejected with `403 Forbidden`.
   - Allowed origins: `http://localhost:*`, `http://127.0.0.1:*`, and `vscode-webview://*`.
3. **Host Header Protection:**
   - Requests with an unrecognized `Host` header (e.g. `Host: attacker.domain`) are rejected with `400 Bad Request` to neutralize DNS rebinding.

---

## 7. Functional rules

### API Routing & Versioning
- **FR-1** `owner`: All programmatic REST endpoints are prefixed with `/api/v1`.
- **FR-2** `baseline`: Static web assets are served from `web/dist/` at `/`. Requests not matching an API route or file fallback to `index.html` (SPA routing).
- **FR-3** `proposal`: The server provides an OpenAPI 3.1 JSON export at `/api/openapi.json` to allow automated frontend client generation.

### Response and Error Contracts
- **FR-4** `proposal`: Every collection response must include `data` and `meta` (containing `limit`, `offset`, and `has_more`).
- **FR-5** `proposal`: All errors must return the standard error envelope with a machine-readable snake_case `code`.
- **FR-6** `proposal`: Validation errors (HTTP 422) return `code: "validation_error"` with field details in `details["fields"]`.

### Security & CORS
- **FR-7** `owner`: By default, the daemon binds only to `127.0.0.1` and `::1`.
- **FR-8** `owner`: Any mutating request (`POST`, `PUT`, `DELETE`, `PATCH`) carrying a non-local `Origin` header must be rejected with HTTP 403 Forbidden.
- **FR-9** `owner`: Safe methods (`GET`, `HEAD`) carrying an untrusted `Origin` header must be rejected with HTTP 403 Forbidden unless the request comes from an allowed local origin or has no Origin header (CLI / desktop curl).
- **FR-10** `proposal`: Request payload size limits:
  - Default JSON payload: maximum 2 MB.
  - Email ingestion endpoint (`/api/v1/ingest/email`): maximum 35 MB to accommodate MIME attachments up to 25 MB.

---

## 8. Data and contracts

### 8.1 Core API Surface (`/api/v1`)

| Method | Path | Summary / Description |
|---|---|---|
| `GET` | `/api/v1/health` | Liveness check; returns `{"status": "ok"}`. |
| `GET` | `/api/v1/status` | System health, database stats, crawler status, and analysis runner state. |
| `GET` | `/api/v1/items` | Query items. Parameters: `source`, `kind`, `course_id`, `q`, `limit`, `offset`. |
| `GET` | `/api/v1/items/{id}` | Detailed single item by compound ID. |
| `GET` | `/api/v1/items/{id}/history` | Historical snapshots of an item. |
| `GET` | `/api/v1/items/{id}/changes` | Detailed change events for an item. |
| `POST` | `/api/v1/items/{id}/label` | Set manual user category/priority label and personal note. |
| `GET` | `/api/v1/upcoming` | Aggregated upcoming deadlines (assignments, quizzes, events) within rolling window. |
| `GET` | `/api/v1/triage` | Triaged queue of incoming emails and announcements with review status. |
| `POST` | `/api/v1/ingest/email` | Ingest email batch from Prospect Mail, Thunderbird, or external script. |
| `GET` | `/api/v1/brightspace/status` | Proxied Brightspace crawler auth state and health metrics. |
| `POST` | `/api/v1/brightspace/sync` | Trigger an on-demand Brightspace synchronization run. |
| `GET` | `/api/v1/files/{sha256}` | Stream binary attachment or document blob by SHA-256. |
| `GET` | `/calendar.ics` | Standard iCalendar subscription feed. |

### 8.2 Standard Error Codes

| Code | HTTP Status | Description |
|---|---|---|
| `item_not_found` | 404 | Requested item ID does not exist in store. |
| `file_not_found` | 404 | Requested blob SHA-256 does not exist on disk. |
| `crawler_unavailable` | 503 | Brightspace crawler daemon is offline or unreachable. |
| `crawler_auth_required` | 401 | Brightspace crawler session expired; user login required. |
| `validation_error` | 422 | Request body failed Pydantic schema validation. |
| `origin_forbidden` | 403 | Request Origin header rejected by security policy. |
| `payload_too_large` | 413 | Request payload exceeded size limit. |

---

## 9. Edge cases and failure modes

| Case | Expected Behaviour |
|---|---|
| **CORS preflight request (`OPTIONS`)** | Respond with allowed methods/headers only if `Origin` is in allowed local list; otherwise return 403. |
| **Missing Content-Type header** | Default to `application/json` for POST endpoints; return 415 Unsupported Media Type if unexpected format. |
| **Crawler service down during query** | Return 503 Service Unavailable with `code: "crawler_unavailable"`; never crash the `campus-assistant` API server. |
| **Compound item ID with special characters** | The `{id}` path parameter supports URL-encoded paths (e.g. `/api/v1/items/email%3Aschool%3Amsg123`). |
| **Malformed JSON body** | Return HTTP 400 Bad Request with `code: "malformed_json"`. |

---

## 10. Non-functional requirements

| Area | Requirement |
|---|---|
| **Latency** | Local read endpoints (`/items`, `/status`, `/upcoming`) must respond in under 15ms for cached/indexed queries. |
| **Concurrency** | Read requests must not be blocked by background ingestion or sync jobs (enforced via SQLite WAL mode). |
| **Security** | Zero data exfiltration vulnerability to malicious third-party websites visited in the user's browser. |
| **Client Usability** | OpenAPI documentation available at `/docs` (Swagger UI) in development mode. |

---

## 11. Compatibility and migration

- **Breaking:** Yes, path prefixes transition from root (`/items`) to `/api/v1/items`.
- **Migration grace period:** Legacy unversioned routes (`/items`, `/status`, `/triage`, `/upcoming`, `/changes`, `/ingest/email`) will issue HTTP 307 Temporary Redirects or be aliased to `/api/v1/*` during v1.0.
- **Frontend migration:** Web UI API client updated to target `/api/v1`.

---

## 12. Acceptance criteria

| ID | Given | When | Then | Test level |
|---|---|---|---|---|
| **AC-1** | The server is running on loopback | A client calls `GET /api/v1/health` | Returns HTTP 200 `{"status": "ok"}` (FR-1) | unit |
| **AC-2** | A web page on `http://malicious-site.com` | Attempts `fetch('http://127.0.0.1:8000/api/v1/items')` | The request is rejected with HTTP 403 Forbidden (FR-8, FR-9) | integration |
| **AC-3** | An invalid item ID is requested | A client calls `GET /api/v1/items/nonexistent` | Returns HTTP 404 with standard error envelope and code `item_not_found` (FR-5) | unit |
| **AC-4** | A collection query is made | A client calls `GET /api/v1/items?limit=10` | Response contains `{ "data": [...], "meta": { "limit": 10, "offset": 0, "has_more": bool } }` (FR-4) | unit |
| **AC-5** | A POST request with 40 MB payload | Sent to `/api/v1/ingest/email` | Returns HTTP 413 Payload Too Large (FR-10) | integration |

---

## 13. Change log

| Date | Change | By |
|---|---|---|
| 2026-10-27 | Initial authoring of local API contract and security specification establishing /api/v1, standard envelopes, and origin validation. | spiralsky & Assistant |

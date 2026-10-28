# Canonical item and source taxonomy

> **Specification state.** Accepted foundational specification establishing the canonical item model, source nomenclature, kind taxonomy, identity hashing, date normalization, and dual body representation for all ingested and referenced entities.

| Field | Value |
|---|---|
| ID | F-002 |
| Status | Accepted |
| Owner | spiralsky |
| Created | 2026-10-27 |
| Last updated | 2026-10-28 |
| Target release | v1.0 |
| Related architecture | Standalone Crawler Service ([`F-019`](F-019-brightspace-crawler.md)), Brightspace Sync ([`F-004`](F-004-automatic-brightspace-sync.md)), Email Ingestion (`F-005`) |
| Supersedes | — |
| Superseded by | — |

**Source key.** `owner` = confirmed by product owner; `baseline` = observed in current implementation; `proposal` = proposed specification.

---

## 1. Summary

The canonical item model is the foundational contract in `campus-assistant`. It defines the unified entity schema, source taxonomy, kind definitions, identity construction, date normalization, and change-hashing rules that represent all incoming information—whether ingested directly (such as emails from Outlook, Thunderbird, or direct mail sync) or queried from external services (such as the Brightspace crawler).

By enforcing strict typing, UTF-8 sanitation, ISO 8601 UTC date formats, and deterministic compound primary keys (`{source}:{kind}:{external_id}`), the canonical taxonomy guarantees that downstream pipelines—including triage classification, task evaluation, search indexing, UI navigation, and calendar feeds—remain clean, consistent, and decoupled from source-specific protocols.

---

## 2. Problem and context

- **Source drift:** Different sources use disparate naming conventions and identifiers. Brightspace uses integer org units and topic IDs; Outlook uses opaque base64 EWS `ItemId` strings; RFC 822 emails use `<message-id@host>` headers. Without a strict normalization layer, identifier collisions and inconsistent IDs degrade change tracking and triage history.
- **Date/Time format inconsistency:** Sources supply dates in varied formats: ISO 8601 with fractional seconds, RFC 2822 email strings (`Mon, 27 Oct 2026 08:00:00 +0000`), local timezone strings without offsets, or Unix epoch timestamps. Lexical sorting and calendar queries fail unless all dates are strictly normalized to UTC ISO 8601 (`YYYY-MM-DDTHH:MM:SSZ`).
- **Text encoding anomalies:** Email bodies and scraped academic documents frequently carry lone surrogates, invalid control characters, or NUL (`\x00`) bytes that cause SQLite insertion errors or crash JSON parsers in the frontend.
- **Decoupled data sources:** With Brightspace data now provided via a standalone crawler daemon ([`F-019`](F-019-brightspace-crawler.md)), `Item` models must distinguish between entities persisted locally (emails, user tasks) and external referenced entities (Brightspace announcements, assignments, quizzes, discussions).

---

## 3. Users and jobs

| User / Consumer | Job / Need | Source |
|---|---|---|
| Triage Engine | Classify incoming items into priority buckets and task types regardless of whether the source is email or Brightspace. | `baseline` |
| Web UI (Inbox, Tasks, Today) | Render unified feeds with sortable dates, source badges, status flags, and attachments without handling raw MIME or Valence payloads. | `owner` |
| Full-text Search & Calendar | Index item titles and bodies with consistent identifiers; generate standard iCalendar feeds with stable UIDs. | `baseline` |
| Downstream Extensions (AI / MCP) | Inspect items via a standardized schema with deterministic fields. | `owner` |

---

## 4. Goals and non-goals

### Goals
- **G-1** `owner`: Define a single, authoritative `Item` schema representing all informational and actionable entities across all sources.
- **G-2** `baseline`: Ensure all item primary keys are globally unique, deterministic, and immutable using the format `{source}:{kind}:{external_id}`.
- **G-3** `baseline`: Strictly normalize all temporal fields (`occurred_at`, `due_at`, `starts_at`, `ends_at`) to UTC `YYYY-MM-DDTHH:MM:SSZ`.
- **G-4** `baseline`: Sanitize strings recursively to eliminate NUL bytes and invalid Unicode surrogates before persistence or serialization.
- **G-5** `proposal`: Separate core identity fields from mutable content and transient metadata to enable deterministic content hashing and change detection.

### Non-goals
- **NG-1** `proposal`: Forcing source-specific idiosyncrasies into top-level columns. Source-specific properties belong in the typed `data` dictionary.
- **NG-2** `owner`: Storing raw binary files inside the `Item` record itself; binaries and attachments are stored as content-addressed file references.

---

## 5. Current behaviour (baseline)

- **Baseline schema (`models.py` / `store.py`):**
  - Columns: `id`, `source`, `kind`, `external_id`, `title`, `body`, `url`, `course_id`, `course_name`, `occurred_at`, `due_at`, `starts_at`, `ends_at`, `data`, `content_hash`, `first_seen`, `last_seen`, `updated_at`, `deleted_at`.
  - Date normalization converts ISO strings and datetimes to `YYYY-MM-DDTHH:MM:SSZ`.
  - `clean_text()` strips NUL bytes and resolves lone UTF-16 surrogates.
  - Compound ID is computed as `{source}:{kind}:{external_id}`.
- **Known gaps:**
  - `source` and `kind` namespaces were unconstrained string fields, leading to loose conventions (`outlook` vs `email:sp_edu`, `assignment` vs `dropbox`).
  - No formal distinction between local stored items and proxied crawler items.
  - Attachment structure in `data["attachments"]` was ad-hoc and inconsistent between email and Brightspace.

---

## 6. Desired behaviour

### 6.1 Source Namespace Taxonomy

Every item's `source` property adheres to a hierarchical, colon-delimited format:
```text
<provider>[:<account_or_instance>]
```

| Source Pattern | Description | Example |
|---|---|---|
| `email:<account>` | Ingested email message from a specific account | `email:school`, `email:personal` |
| `outlook` | Legacy alias for Prospect Mail / Outlook ingestion | `outlook` |
| `brightspace:<host>` | Brightspace entity proxied or referenced from crawler | `brightspace:splms.polite.edu.sg` |
| `manual` | User-authored task or personal note | `manual:personal` |
| `system` | System alerts, diagnostics, or sync notifications | `system:core` |

### 6.2 Kind Taxonomy

Every item has an explicit `kind` from the following standardized taxonomy:

| Kind | Description | Key Temporal Field | Primary Use Case |
|---|---|---|---|
| `email` | Ingested email message | `occurred_at` (Received date) | Inbox, Triage |
| `announcement` | Course or institutional news announcement | `occurred_at` (Posted date) | Inbox, Today view |
| `assignment` | Course assignment, submission dropbox, or lab task | `due_at`, `ends_at` | Tasks, Upcoming, Briefs |
| `quiz` | Quiz, exam, test, or knowledge check | `due_at`, `starts_at`, `ends_at` | Tasks, Calendar |
| `event` | Calendar event, lecture session, or appointment | `starts_at`, `ends_at` | Calendar, Today view |
| `content` | Course slide, syllabus, reading, or module document | `occurred_at` (Modified date) | Browse, Search, Brief context |
| `grade` | Gradebook entry, score, or instructor feedback | `occurred_at` (Graded date) | Academic performance |
| `discussion` | Discussion topic, thread, or forum post | `occurred_at` (Posted date) | Discussions, Collaboration |
| `checklist` | Checklist container or item checklist | `due_at` | Tasks, Tracking |
| `task` | Standalone student task or action item | `due_at` | Tasks view |

---

## 7. Functional rules

### Identity and Keys
- **FR-1** `baseline`: The canonical item ID is immutable, globally unique, and constructed as:
  ```text
  {source}:{kind}:{external_id}
  ```
- **FR-2** `baseline`: `external_id` must be stable within that `source` and `kind`. If the source provides a volatile or variable-length key (e.g. EWS `ItemId`), it must be deterministically hashed (e.g. SHA-1/SHA-256 hex digest) before forming `external_id`.
- **FR-3** `owner`: For email items, `external_id` is the canonical `Message-ID` (sanitized of surrounding `<>`), or `sha1(sender + date + subject)[:16]` if `Message-ID` is absent.
- **FR-3.1** `owner`: `course_id` foreign keys must use a hierarchical namespace format `{provider}:{course_code_or_id}` (e.g. `brightspace:12345` or `sp:ST0257`) to avoid collisions across multiple LMS instances or institutions.
- **FR-3.2** `owner`: Strict Enum / taxonomy validation is enforced at ingestion and API boundaries. Unrecognized `kind` values or source provider prefixes are rejected with a validation error.

### Temporal Fields and Normalization
- **FR-4** `baseline`: All date fields (`occurred_at`, `due_at`, `starts_at`, `ends_at`) must be stored as UTC ISO 8601 strings in the exact format:
  ```text
  YYYY-MM-DDTHH:MM:SSZ
  ```
- **FR-5** `baseline`: If a date has fractional seconds (e.g. `.123Z`), the fractional seconds are truncated.
- **FR-6** `baseline`: If an incoming date lacks timezone information, it is interpreted as UTC by default unless an explicit user timezone offset is configured.
- **FR-6.1** `owner`: If an upstream date string is missing, invalid, or cannot be parsed into an ISO timestamp, the temporal field is set to `None`, and a warning is logged in `data["warnings"]`. Ingestion never crashes or silently fabricates synthetic dates.

### Text Sanitation and Body Fields
- **FR-7** `baseline`: All strings within `title`, `body_text`, `body_html`, and `data` are recursively sanitized before acceptance:
  - NUL characters (`\x00`) are removed.
  - Lone UTF-16 surrogates are replaced with valid UTF-8 replacement characters (`\ufffd`).
- **FR-8** `owner`: `Item` models maintain explicit dual body fields:
  - `body_text`: Plain text representation (or clean Markdown) for search indexing, LLM prompts, preview snippets, and terminals.
  - `body_html`: Sanitized HTML content (optional, `str | None`) preserving original tables, links, and layout for rich UI rendering.
  - For backward compatibility during migration, accessing legacy `body` proxies to `body_text`.

### Content Hashing & Change Detection
- **FR-9** `baseline`: `content_hash` is computed as the SHA-256 hex digest over the normalized, sorted JSON representation of meaningful content fields:
  ```json
  ["title", "body_text", "body_html", "url", "course_id", "course_name", "occurred_at", "due_at", "starts_at", "ends_at", "data_meaningful"]
  ```
- **FR-10** `baseline`: Ephemeral attributes (such as `raw`, `meta`, `last_crawled`, or crawler-internal timestamps) are excluded from `content_hash` calculation to avoid false change events.

---

## 8. Data and contracts

### 8.1 Unified Item Model (`Item`)

```python
class Item(BaseModel):
    id: str                       # Computed: "{source}:{kind}:{external_id}"
    source: str                   # e.g. "email:school", "brightspace:splms" (validated provider prefix)
    kind: str                     # e.g. "email", "assignment", "quiz" (strictly validated taxonomy Enum)
    external_id: str              # Stable source-specific identifier
    title: str                    # Sanitized plain text title/subject
    body_text: str                # Sanitized plain text / Markdown content
    body_html: str | None = None  # Optional sanitized HTML content for rich rendering
    url: str | None = None        # Canonical web link to upstream item
    course_id: str | None = None  # Hierarchical course reference: "{provider}:{course_id}"
    course_name: str | None = None
    occurred_at: str | None = None # UTC ISO8601 (YYYY-MM-DDTHH:MM:SSZ)
    due_at: str | None = None      # UTC ISO8601 (YYYY-MM-DDTHH:MM:SSZ)
    starts_at: str | None = None   # UTC ISO8601 (YYYY-MM-DDTHH:MM:SSZ)
    ends_at: str | None = None     # UTC ISO8601 (YYYY-MM-DDTHH:MM:SSZ)
    data: dict[str, Any] = Field(default_factory=dict)

    @property
    def body(self) -> str:
        """Backward-compatibility alias pointing to body_text."""
        return self.body_text
```

### 8.2 Standard Attachment Structure (`data["attachments"]`)

When items carry binary attachments (such as email documents or assignment briefs), they must adhere to the standard schema:

```json
[
  {
    "id": "att-1",
    "filename": "Lab1_Specification.pdf",
    "content_type": "application/pdf",
    "byte_size": 204850,
    "sha256": "3a7b...",
    "url": "/api/files/3a7b...",
    "is_inline": false
  }
]
```

### 8.3 Kind-Specific Attributes in `data`

| Kind | Required / Standard `data` Keys |
|---|---|
| `email` | `sender` (str), `to` (list[str]), `cc` (list[str]), `message_id` (str), `folder` (str), `attachments` (list) |
| `assignment` | `dropbox_id` (str), `max_points` (float), `submitted` (bool), `last_submitted_at` (str), `rubric` (dict) |
| `quiz` | `time_limit_mins` (int), `attempts_allowed` (int), `attempts_taken` (int), `score` (float) |
| `grade` | `points_earned` (float), `points_possible` (float), `weight` (float), `grade_text` (str) |
| `discussion` | `forum_id` (str), `topic_id` (str), `thread_id` (str), `author_name` (str), `is_read` (bool) |

---

## 9. Edge cases and failure modes

| Case | Expected Behaviour |
|---|---|
| **Missing Title** | If an email or post has no subject/title, default to `"(No subject)"` or truncated body text. |
| **Duplicate Ingestion** | If an identical `Item` is ingested with the same `content_hash`, the store updates `last_seen` only; no history row or change event is generated. |
| **Invalid Date String** | If an upstream date string cannot be parsed into an ISO timestamp, record `None` for the date field and log a parse warning; never crash ingestion. |
| **Lone Surrogates / NULs** | Automatically cleaned via UTF-16 surrogatepass / replace logic. |
| **Massive Body Text** | Body text exceeding 100,000 characters is truncated with an indicator `[... truncated for storage]`; full raw MIME or file remains referenced. |

---

## 10. Non-functional requirements

| Area | Requirement |
|---|---|
| **Performance** | Ingesting and normalizing a batch of 100 items must take under 100ms in-process. |
| **Data Integrity** | Item ID generation must be strictly deterministic: repeating ingestion of identical raw items always generates identical IDs. |
| **Security** | Raw HTML stored in `body_html` is treated as untrusted and must be sanitized (stripping `<script>`, `<iframe>`, and event handlers) before rendering in web views. |

---

## 11. Compatibility and migration

- **Breaking:** Minor additive change.
- **What changes:** Codifies existing `ItemIn` patterns into an authoritative contract, introducing explicit `body_text` and `body_html` fields with a `@property def body` fallback for legacy code.
- **Existing data:** Current SQLite records in `items` table already follow `{source}:{kind}:{external_id}`. A column addition or alias for `body_text` / `body_html` maintains zero data loss.
- **Migration:** Backwards-compatible; `body` in existing records maps to `body_text`.

---

## 12. Acceptance criteria

| ID | Given | When | Then | Test level |
|---|---|---|---|---|
| **AC-1** | An email with Message-ID `<abc@domain.com>` and account `school` | Normalized into an `Item` | `item.id` equals `email:school:abc@domain.com` (FR-1, FR-3) | unit |
| **AC-2** | An incoming date string `"2026-10-27T16:00:00.123456+08:00"` | Converted via date normalizer | The resulting date is `"2026-10-27T08:00:00Z"` (FR-4, FR-5) | unit |
| **AC-3** | A body containing NUL byte `"\x00"` and a lone surrogate `"\ud800"` | Cleaned via text sanitation | NUL is deleted and surrogate is replaced with `\ufffd` without raising `UnicodeEncodeError` (FR-7) | unit |
| **AC-4** | Two identical items with the same data ingested consecutively | Evaluated for changes | The second item computes the identical `content_hash` and generates zero change records (FR-9, FR-10) | unit |
| **AC-5** | An item carrying binary attachments | Attached into `data["attachments"]` | Each attachment matches the standard attachment structure with SHA-256 and content type (FR-8) | unit |
| **AC-6** | An item with missing/unparseable date | Normalized into an `Item` | Temporal field is set to `None` and warning recorded in `data["warnings"]` without crashing (FR-6.1) | unit |
| **AC-7** | An item with unapproved kind or unknown source prefix | Validated against taxonomy | Schema raises strict validation error rejecting the item (FR-3.2) | unit |

---

## 15. Open questions and decisions

| ID | Question | Owner | Resolution | Date |
|---|---|---|---|---|
| **Q-002-01** | How strictly should `source` and `kind` be validated at ingestion/API boundaries? | spiralsky | Strict Enum validation: reject any item with unrecognized source prefixes or kinds at ingestion/API boundary. | 2026-10-28 |
| **Q-002-02** | How should email & LMS bodies (HTML vs plain text) be stored in `Item`? | spiralsky | Dual top-level fields: add explicit `body_text` and `body_html` fields on Item, with legacy `body` proxying to `body_text`. | 2026-10-28 |
| **Q-002-03** | How should `course_id` foreign keys be structured? | spiralsky | Hierarchical course ID: e.g. `brightspace:12345` or `sp:ST0257` to prevent collisions across multiple LMS instances. | 2026-10-28 |
| **Q-002-04** | How should missing or unparseable temporal fields be handled? | spiralsky | Strict ISO-8601: normalize to UTC ISO-8601. If missing or unparseable, set to `None` and log a warning in `data["warnings"]` without fabricating timestamps. | 2026-10-28 |

---

## 16. Out of scope / future work

- Bi-directional schema conversion to proprietary external calendar formats outside iCalendar.
- Automatic multilingual translation of body text during taxonomy normalization.

---

## 17. Change log

| Date | Change | By |
|---|---|---|
| 2026-10-27 | Initial authoring of canonical item and source taxonomy specification | spiralsky & Assistant |
| 2026-10-28 | Resolved Q-002-01 through Q-002-04; updated Item schema to dual body fields; advanced status to Accepted | spiralsky & Assistant |

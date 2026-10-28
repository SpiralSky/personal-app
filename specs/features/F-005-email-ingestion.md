# Email ingestion and archive import

> **Specification state.** Draft establishing multi-source email ingestion across Prospect Mail archives/push, Mozilla Thunderbird local profiles/exports, and direct in-app mail accounts.

| Field | Value |
|---|---|
| ID | F-005 |
| Status | Draft |
| Owner | spiralsky |
| Created | 2026-10-27 |
| Last updated | 2026-10-27 |
| Target release | v1.0 |
| Related architecture | Canonical Item Taxonomy ([`F-002`](F-002-canonical-item-taxonomy.md)), Local API Contract (`F-015`) |
| Supersedes | — |
| Superseded by | — |

**Source key.** `owner` = confirmed by product owner; `baseline` = observed in current implementation; `proposal` = proposed specification.

---

## 1. Summary

This specification defines the email ingestion pipeline for `campus-assistant`. It provides a flexible, modular ingestion architecture supporting three distinct email sources:
1. **Prospect Mail** (pushing via HTTP webhook or bulk-importing from archive folders).
2. **Mozilla Thunderbird** (importing local `.eml` exports or scanning maildir/profile folders).
3. **Direct Mail Accounts** (built-in background IMAP / Microsoft Graph polling).

Incoming messages are parsed from RFC 822 MIME (or HTML fallback), sanitized, normalized into canonical `Item` records under the source namespace `email:<account>`, and indexed into the local SQLite store. Attachments up to 25 MB are preserved as deduplicated content-addressed binary blobs (SHA-256), while accounts remain strictly isolated to allow distinct tracking of multi-inbox workflows.

---

## 2. Problem and context

- **Client fragmentation:** Users often manage multiple email accounts across diverse email clients: school accounts via custom Electron clients (Prospect Mail fork), desktop archives via Thunderbird, or standalone IMAP/Outlook setups.
- **Fragile coupling in baseline:** The existing `mail.py` was hardcoded exclusively for Prospect Mail's specific `index.json` structure and single source identifier (`"outlook"`). It could not distinguish separate accounts, did not save binary attachments, and lacked integration for standard email clients like Thunderbird.
- **Attachment data loss:** Previously, email attachments only recorded filename and MIME type. Users could not preview, download, or run document analysis on slide attachments or assignment PDFs sent via email.
- **Account isolation need:** A user receiving the same course announcement or newsletter in both their university inbox and personal inbox needs each account's triage state, folder context, and read flags tracked independently.

---

## 3. Users and jobs

| User / Consumer | Job / Need | Source |
|---|---|---|
| Student (User) | Aggregate school emails, club announcements, and personal messages into a single triage inbox without changing daily mail clients. | `owner` |
| Prospect Mail Fork | Send archived messages in real time via HTTP webhook or allow batch import of archive folders. | `owner` |
| Thunderbird User | Import historical mail folders or watch local exported maildirs without exposing account credentials. | `owner` |
| Standalone User | Authenticate an IMAP / Graph account directly within `campus-assistant` for zero-maintenance background syncing. | `owner` |
| Triage & Planning Engine | Classify incoming messages, detect deadlines, and extract task briefs from email body text and attachments. | `baseline` |

---

## 4. Goals and non-goals

### Goals
- **G-1** `owner`: Multi-source architecture supporting Prospect Mail archive/webhook, Mozilla Thunderbird import/drop, and direct IMAP/Graph accounts.
- **G-2** `owner`: Strict account isolation: items are partitioned under `email:<account>` (e.g. `email:school`, `email:personal`) so duplicate messages across different accounts are preserved independently.
- **G-3** `owner`: Store binary email attachments up to 25 MB as content-addressed blobs keyed by SHA-256 in local storage.
- **G-4** `baseline`: Accept RFC 822 MIME raw bytes (preferred) with automatic fallback to rendered HTML + metadata payloads.
- **G-5** `baseline`: Extract structured metadata for triage (Mailing List IDs, bulk headers, `Auto-Submitted`, `From`, `To`, `Cc`, `Reply-To`).

### Non-goals
- **NG-1** `owner`: Full interactive email composition or outgoing SMTP client in v1 (read and triage only; replies open in system mail client).
- **NG-2** `proposal`: Full bidirectional folder synchronization (e.g. deleting an email in `campus-assistant` does not delete it from upstream IMAP unless explicitly configured in future versions).
- **NG-3** `proposal`: Downloading attachments larger than 25 MB (placeholders recorded with `skipped: true`).

---

## 5. Current behaviour (baseline)

- **Endpoints:** `POST /ingest/email` accepts a batch of JSON objects (`account`, `item_id`, `key`, `folder`, `mime_base64`, `html`, `received_at`, etc.).
- **Deduplication:** Uses `short_hash(item_id)` = `sha1(EWS_ItemId)[:16]` as `external_id`.
- **Source:** Hardcoded to `"outlook"`.
- **Parsing:** Parses RFC 822 using `email.parser.BytesParser`, extracts plain text and HTML via `html_to_text()`, and caps body text at 100,000 characters.
- **Attachments:** Recorded in `data["attachments"]` as a list of `{"name": ..., "type": ..., "size": ...}`; binaries were discarded.

---

## 6. Desired behaviour

### 6.1 Ingestion Adapters

#### Adapter 1: HTTP Push Webhook (`POST /api/ingest/email`)
- External clients (Prospect Mail, Thunderbird export scripts, curl) post single messages or batches.
- Payloads can supply raw MIME as `mime_base64` or pre-parsed fields (`subject`, `from`, `body_html`, `attachments`).

#### Adapter 2: Prospect Mail Archive Importer (`campus import-mail`)
- Scans configured archive directories containing `index.json`, `.eml`, `.html`, and `.json` files.
- Reads account folders, processes unindexed messages, and stores deduplicated items.

#### Adapter 3: Thunderbird & Local Maildir Drop Watcher
- Watches a designated directory (e.g. `~/.local/share/campus-assistant/drop/email/<account>/` or Thunderbird profile exported folders).
- Auto-ingests `.eml` files dropped into the folder, moves processed files to `processed/` or retains them in place.

#### Adapter 4: Direct IMAP / Graph Sync (Background Engine)
- Configured in `config.json` with host, port, TLS, username, and password/token.
- Background worker connects on startup and interval (default: every 15 minutes), fetches new messages via `UID FETCH`, and feeds them to the parser.

### 6.2 Attachment Processing
- Attachments in MIME parts are decoded.
- If payload $\le$ 25 MB:
  - Compute SHA-256.
  - Store binary in `<data_dir>/blobs/sha256/xx/yy/<hash>`.
  - Record reference in `data["attachments"]` with file metadata, `sha256`, and streaming URL `/api/files/{sha256}`.
- If payload $>$ 25 MB:
  - Skip binary write; record attachment entry with `oversized: true`.

---

## 7. Functional rules

### Identity and Namespacing
- **FR-1** `owner`: The source namespace is `email:<account_name>` (e.g. `email:school`, `email:personal`). If unspecified in payload, default is `email:default`. Legacy `"outlook"` is treated as alias for `email:outlook`.
- **FR-2** `owner`: Within an account, the canonical `external_id` is derived in precedence order:
  1. Header `Message-ID` (normalized: lowercase, stripped of `<>` and outer whitespace).
  2. Prospect Mail index `key` or `sha1(EWS_ItemId)[:16]`.
  3. Hash fallback: `sha256(sender + "|" + received_date + "|" + subject)[:24]`.
- **FR-3** `owner`: Deduplication is scoped strictly to the account. If the same `Message-ID` exists in `email:personal` and `email:school`, two distinct `Item` records are maintained.

### Parsing and Body Extraction
- **FR-4** `baseline`: When MIME payload is provided, the message body is extracted with preference: `text/plain` $\rightarrow$ `text/html` converted to plain text.
- **FR-5** `baseline`: Body text is capped at 100,000 characters. If truncated, an indicator `[... truncated]` is appended.
- **FR-6** `proposal`: The original HTML content is preserved in `data["body_html"]` for rich email rendering in the UI.

### Attachment Ingestion
- **FR-7** `owner`: Non-inline attachments up to 25 MB are stored in blob storage keyed by SHA-256.
- **FR-8** `owner`: Duplicate attachments across messages (or courses) share a single physical blob file on disk.
- **FR-9** `proposal`: Inline images (`Content-Disposition: inline` or carrying a `Content-ID`) are also saved to blob storage and rewritten as local URLs in `body_html`.

### Header Signals & Classification
- **FR-10** `baseline`: The parser extracts bulk and automated mail signals into `data`:
  - `is_bulk`: `true` if `List-Unsubscribe` header exists or `Precedence: bulk/list`.
  - `is_auto`: `true` if `Auto-Submitted` header is not `no` or `""`.
  - `list_id`: sanitized value of `List-Id` header.

---

## 8. Data and contracts

### 8.1 Ingestion API Schema (`POST /api/ingest/email`)

```python
class EmailAttachmentIn(BaseModel):
    filename: str
    content_type: str
    data_base64: str | None = None  # Base64 encoded payload
    byte_size: int | None = None

class EmailMessageIn(BaseModel):
    account: str = "default"        # Maps to source "email:<account>"
    message_id: str | None = None   # RFC 822 Message-ID
    item_id: str | None = None      # External client id (e.g. EWS ItemId)
    key: str | None = None          # Archive key
    folder: str = "INBOX"           # Folder / mailbox tag
    received_at: str | None = None  # UTC ISO timestamp
    subject: str = ""
    sender: str | None = None
    to: list[str] = Field(default_factory=list)
    cc: list[str] = Field(default_factory=list)
    mime_base64: str | None = None  # Full RFC 822 raw message
    html: str | None = None
    body_text: str | None = None
    attachments: list[EmailAttachmentIn] = Field(default_factory=list)

class EmailBatchIn(BaseModel):
    messages: list[EmailMessageIn]
```

### 8.2 Stored Item Schema Representation

Ingesting a message produces a standard `Item` ([`F-002`](F-002-canonical-item-taxonomy.md)):
- `id`: `email:<account>:<external_id>`
- `source`: `email:<account>`
- `kind`: `"email"`
- `title`: Subject line (or `"(No subject)"`)
- `body`: Plain text body
- `occurred_at`: Received timestamp in UTC ISO format
- `data`:
  ```json
  {
    "account": "school",
    "folder": "INBOX",
    "sender": "Professor Smith <smith@university.edu>",
    "to": ["student@university.edu"],
    "cc": [],
    "message_id": "CABc123@mail.gmail.com",
    "is_bulk": false,
    "is_auto": false,
    "has_mime": true,
    "body_html": "<p>Lecture slides attached...</p>",
    "attachments": [
      {
        "filename": "Week9.pdf",
        "content_type": "application/pdf",
        "byte_size": 1542000,
        "sha256": "8f3b...",
        "url": "/api/files/8f3b..."
      }
    ]
  }
  ```

---

## 9. Edge cases and failure modes

| Case | Expected Behaviour |
|---|---|
| **Corrupted MIME message** | Log warning with parse error; attempt regex/header fallback for Subject and Date; store unparsed raw body if possible. |
| **Missing Message-ID and Date** | Compute fallback hash from `sha256(sender + subject + body[:100])[:24]`; never reject an email solely due to missing standard headers. |
| **Attachment exceeds 25 MB** | Binary payload is not saved to disk; attachment record is written with `skipped: true` and `reason: "exceeds_max_size_25mb"`. |
| **Disk space low (< 500 MB)** | Refuse new binary attachment writes; record email metadata and text body only with a warning log. |
| **Character encoding errors** | Sanitize all text via UTF-16 surrogatepass/replace to prevent database insertion failure. |

---

## 10. Non-functional requirements

| Area | Requirement |
|---|---|
| **Performance** | Ingesting and parsing an RFC 822 email with a 5 MB PDF attachment must complete in under 50ms. |
| **Storage Limits** | Maximum default individual attachment size: 25 MB. Maximum body character count: 100,000. |
| **Privacy** | Mail credentials (IMAP passwords, tokens) are stored in secure local configuration with restricted file permissions (`chmod 600`). No email content leaves the local machine. |
| **Observability** | Ingestion batches log total processed, newly created, updated, and skipped counts. |

---

## 11. Compatibility and migration

- **Breaking:** Minor.
- **What changes:** `source` values transition from `"outlook"` to `email:<account>`. The ingestion endpoint accepts `"outlook"` as an alias for backwards compatibility with existing Prospect Mail push scripts.
- **Existing data:** Existing items in the store with `source: "outlook"` remain readable and queryable.
- **Migration:** Optional CLI command `campus migrate-mail-sources` updates legacy `"outlook"` records to `email:outlook`.

---

## 12. Acceptance criteria

| ID | Given | When | Then | Test level |
|---|---|---|---|---|
| **AC-1** | A raw RFC 822 `.eml` payload posted to `/api/ingest/email` with account `"school"` | Processed by ingestion pipeline | A canonical `Item` with `id: "email:school:<msg_id>"` is saved in the store (FR-1, FR-2) | integration |
| **AC-2** | Two distinct accounts `"school"` and `"personal"` receive the same message with identical `Message-ID` | Both messages are ingested | Two separate `Item` rows exist (`email:school:...` and `email:personal:...`) (FR-3) | integration |
| **AC-3** | An email containing a 2 MB PDF attachment is ingested | MIME is parsed | The PDF binary is saved in content-addressed blob storage and referenced via SHA-256 in `data["attachments"]` (FR-7, FR-8) | integration |
| **AC-4** | An email containing a 30 MB ZIP attachment is ingested | MIME is parsed | The email body is ingested, the attachment binary is skipped, and `oversized: true` is set (FR-7) | unit |
| **AC-5** | A message containing bulk mailing list headers (`List-Unsubscribe`) | Ingested into store | `item.data["is_bulk"]` is set to `true` (FR-10) | unit |

---

## 13. Open questions and decisions

| ID | Question | Owner | Resolution | Date |
|---|---|---|---|---|
| **Q-1** | Should attachment text be indexed into FTS search immediately upon email ingestion? | spiralsky | **Resolved**: Optional background task; queue document text extraction for PDF/DOCX attachments matching crawler FTS schema. | 2026-10-27 |
| **Q-2** | How should Thunderbird local maildirs be configured? | spiralsky | **Resolved**: Support both an explicit folder drop directory (`campus-assistant/drop/email/<account>`) and direct file import CLI (`campus import-mail --format eml <path>`). | 2026-10-27 |

---

## 14. Change log

| Date | Change | By |
|---|---|---|
| 2026-10-27 | Initial authoring of multi-source email ingestion specification supporting Prospect Mail, Thunderbird, and direct accounts with 25MB attachment blobs. | spiralsky & Assistant |

# Change tracking and history

> **Specification state.** Draft establishing change detection, historical version snapshots, field-level diff logs, soft-deletion semantics, and retention policies across all persisted items.

| Field | Value |
|---|---|
| ID | F-003 |
| Status | Draft |
| Owner | spiralsky |
| Created | 2026-10-27 |
| Last updated | 2026-10-27 |
| Target release | v1.0 |
| Related architecture | Canonical Item Taxonomy ([`F-002`](F-002-canonical-item-taxonomy.md)), Email Ingestion ([`F-005`](F-005-email-ingestion.md)), Brightspace Sync ([`F-004`](F-004-automatic-brightspace-sync.md)) |
| Supersedes | — |
| Superseded by | — |

**Source key.** `owner` = confirmed by product owner; `baseline` = observed in current implementation; `proposal` = proposed specification.

---

## 1. Summary

This specification defines the change tracking and version history engine for `campus-assistant`. Every persisted item is tracked across its lifecycle: creation, non-destructive field updates, soft-deletion upon removal from an upstream source, and restoration. 

Change detection relies on deterministic content hashing (`content_hash`) over meaningful semantic fields. When an item changes, a full JSON snapshot of its previous state is preserved in `item_history`, and an immutable event is written to `changes` detailing the exact changed field names (e.g. `due_at`, `title`, `data.folder`). This architecture enables timeline inspection ("When did the lecturer change the assignment deadline?"), non-destructive synchronization, automated cache invalidation for LLM analyses, and safe rollback.

---

## 2. Problem and context

- **Silent upstream modifications:** Academic deadlines, lecture slides, and assignment rubrics are frequently altered by instructors without separate notifications. Without change tracking, users have no visibility into what changed or when an exam date was rescheduled.
- **Cache invalidation for AI pipelines:** Downstream triage analyses and task briefs depend on LLM evaluations. If an item changes (e.g. email thread receives an update or an assignment description changes), the system must detect the change to invalidate stale analyses without re-running expensive LLM tasks on unchanged items.
- **Accidental deletion risk:** Upstream items may disappear temporarily due to network timeouts, filtered API endpoints, or pagination errors. Hard-deleting rows on missing items destroys triage notes and user labels.
- **Auditability:** Users need to answer questions like: "What was the previous submission deadline?", "Did the instructor add new files?", or "Was this email moved out of INBOX?".

---

## 3. Users and jobs

| User / Consumer | Job / Need | Source |
|---|---|---|
| Student (User) | See an audit log of changes ("Due date moved from Friday to Sunday") and view previous versions of an item. | `owner` |
| Triage & Planning Pipeline | Invalidate cached LLM briefs and re-evaluate triage priority only when meaningful content changes. | `baseline` |
| Sync Engines (Email & Crawler) | Safely update stored records without overwriting user notes or creating duplicate history entries. | `baseline` |
| Calendar Exporter | Distinguish between a newly scheduled event and a rescheduled event with updated start/end times. | `proposal` |

---

## 4. Goals and non-goals

### Goals
- **G-1** `baseline`: Detect item modifications via deterministic SHA-256 `content_hash` over canonical content fields, ignoring ephemeral metadata.
- **G-2** `baseline`: Preserve complete historical versions in `item_history` before overwriting an existing record.
- **G-3** `baseline`: Record an append-only timeline in `changes` logging the transition type (`created`, `updated`, `removed`, `restored`) and the specific field names that differed.
- **G-4** `baseline`: Implement soft-deletion (`deleted_at IS NOT NULL`) for removed items; never permanently delete records during routine sync.
- **G-5** `proposal`: Support configurable history retention (pruning snapshots older than $N$ days while keeping current records and change event logs).

### Non-goals
- **NG-1** `proposal`: Full Git-like branch-and-merge or manual conflict resolution; the upstream source or user edit is always authoritative.
- **NG-2** `proposal`: Storing binary diffs or delta compression for text bodies; full JSON snapshots are stored in `item_history`.
- **NG-3** `owner`: Versioning external crawler items that are not persisted in `campus_assistant.db` (crawler versioning is governed by `F-019`).

---

## 5. Current behaviour (baseline)

- **Storage (`store.py`):**
  - Table `items`: Contains current state, `content_hash`, `first_seen`, `last_seen`, `updated_at`, `deleted_at`.
  - Table `item_history`: Captures previous full JSON row snapshot, keyed by `(item_id, content_hash, replaced_at)`.
  - Table `changes`: Logs `(id, item_id, at, change, fields)` where `change` is `created | updated | removed | restored` and `fields` is a JSON array of changed field names.
- **Hashing rules:**
  - Tracked columns: `title`, `body`, `url`, `course_name`, `occurred_at`, `due_at`, `starts_at`, `ends_at`, and `data` (excluding keys `"raw"` and `"meta"`).
- **Soft deletion (`mark_missing`):**
  - Items not returned in a complete fetch are soft-deleted by setting `deleted_at = now`.
  - Re-appearing items have `deleted_at` set back to `NULL` and log change `restored`.

---

## 6. Desired behaviour

### 6.1 Ingestion & Upsert Flow
1. An incoming `Item` is submitted to `Store.upsert(item)`.
2. The store computes `new_hash = content_hash(item)`.
3. If no row exists:
   - Insert new row with `first_seen = last_seen = updated_at = now`.
   - Log `changes` event with `change: "created"`, `fields: []`.
4. If row exists and `deleted_at IS NOT NULL` (previously soft-deleted):
   - Update `deleted_at = NULL`, `updated_at = now`, `last_seen = now`.
   - Log `changes` event with `change: "restored"`.
5. If row exists and `row.content_hash == new_hash`:
   - Update `last_seen = now` and refresh unhashed data (`meta`).
   - Emit status `"unchanged"`; write no rows to `item_history` or `changes`.
6. If row exists and `row.content_hash != new_hash`:
   - Determine diff: compare tracked fields and nested `data` keys to generate `fields = ["due_at", "data.attachments"]`.
   - Insert old row snapshot into `item_history`.
   - Update `items` with new fields, `new_hash`, and `updated_at = now`.
   - Log `changes` event with `change: "updated"`, `fields: fields`.
   - Invalidate cached LLM entries in `analyses` table matching `item_id`.

### 6.2 Soft-Deletion Flow (`mark_missing`)
1. When a source runs a complete ingestion cycle (e.g. fetching all messages in a mailbox folder), it provides the set of all active IDs.
2. Any item belonging to that source and scope currently not marked deleted that is missing from the active set is marked:
   - `deleted_at = now`.
   - Log `changes` event with `change: "removed"`, `fields: []`.
3. Soft-deleted items are excluded from active UI views (Inbox, Today, Upcoming) by default, but remain queryable via `?include_deleted=true` and in historical audit logs.

---

## 7. Functional rules

### Change Detection
- **FR-1** `baseline`: `content_hash` is computed as:
  $$\text{SHA-256}(\text{json\_dumps}(h, \text{sort\_keys}=\text{true}))$$
  where $h$ contains tracked top-level fields (`title`, `body`, `url`, `course_name`, `occurred_at`, `due_at`, `starts_at`, `ends_at`) and `data` with ephemeral keys removed.
- **FR-2** `baseline`: The keys `"raw"` and `"meta"` in `data` are strictly excluded from change hashing.
- **FR-3** `proposal`: Whitespace trimming: trailing whitespace differences in `title` do not constitute a meaningful change.

### Diff Reporting
- **FR-4** `baseline`: Changes between old and new state are recorded as a sorted JSON list of field names. Nested keys within `data` are formatted using dot notation (e.g. `data.folder`, `data.attachments`).
- **FR-5** `baseline`: Transition types in `changes` are strictly restricted to:
  - `created`: First time item is stored.
  - `updated`: Existing active item whose `content_hash` changed.
  - `removed`: Existing item missing from a complete source fetch (soft-deleted).
  - `restored`: Previously soft-deleted item re-appearing in a source fetch.

### Analysis & Cache Invalidation
- **FR-6** `proposal`: When an item receives an `updated` event where meaningful fields changed, existing rows in `analyses` table for that `item_id` are purged or marked stale to trigger re-evaluation.
- **FR-7** `proposal`: If an update touches only `data.folder` or `url`, content-based LLM analyses (e.g. brief, triage category) are not invalidated.

### Retention & Pruning
- **FR-8** `proposal`: Soft-deleted items are retained indefinitely by default, or pruned only when explicitly requested via `campus prune --deleted-before <date>`.
- **FR-9** `proposal`: Historical snapshots in `item_history` older than 90 days can be pruned via retention maintenance, retaining at least the 2 most recent snapshots for any item.

---

## 8. Data and contracts

### 8.1 SQLite Relational Schema

```sql
CREATE TABLE items (
    id            TEXT PRIMARY KEY,
    source        TEXT NOT NULL,
    kind          TEXT NOT NULL,
    external_id   TEXT NOT NULL,
    title         TEXT NOT NULL DEFAULT '',
    body          TEXT NOT NULL DEFAULT '',
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

CREATE TABLE item_history (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id      TEXT NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    content_hash TEXT NOT NULL,
    snapshot     TEXT NOT NULL,     -- Full JSON representation of previous items row
    replaced_at  TEXT NOT NULL      -- UTC ISO8601
);

CREATE TABLE changes (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id TEXT NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    at      TEXT NOT NULL,          -- UTC ISO8601
    change  TEXT NOT NULL,          -- created | updated | removed | restored
    fields  TEXT NOT NULL DEFAULT '[]' -- JSON array of strings
);
```

### 8.2 Change Query API

| Method | Path | Summary / Description |
|---|---|---|
| `GET` | `/api/items/{id}/history` | Retrieve chronological version snapshots of an item. |
| `GET` | `/api/items/{id}/changes` | Retrieve list of change events and modified field names. |
| `GET` | `/api/changes` | Unified timeline of recent modifications across all items. Query: `since`, `change_type`, `limit`. |

---

## 9. Edge cases and failure modes

| Case | Expected Behaviour |
|---|---|
| **Rapid successive updates** | Multiple updates within seconds each record a snapshot in `item_history` with unique timestamps and distinct content hashes. |
| **Flapping / intermittent sync** | If a source alternately returns and omits an item due to network flakiness, `mark_missing` should only soft-delete if the fetch was marked `complete: true`. Partial sync runs must not invoke `mark_missing`. |
| **Identical content, different metadata** | Updating only `data.meta.eml_path` leaves `content_hash` untouched; `last_seen` and `data` are updated in place with zero history rows generated. |
| **Database rollback mid-batch** | In `upsert_many()`, batch execution is wrapped in an atomic transaction (`BEGIN / COMMIT`). Any unhandled error triggers `ROLLBACK`, leaving zero orphan history rows. |

---

## 10. Non-functional requirements

| Area | Requirement |
|---|---|
| **Performance** | Computing `content_hash` and field diff must take less than 0.5ms per item. Batch upsert of 500 items in a single transaction must take under 100ms. |
| **Storage Overhead** | `item_history` snapshots store compressed or plain JSON; on a typical semester mailbox (~5,000 items), history overhead must not exceed 25 MB. |
| **Integrity** | Foreign keys with `ON DELETE CASCADE` ensure that purging a soft-deleted item cleans associated `item_history` and `changes` records. |

---

## 11. Compatibility and migration

- **Breaking:** No.
- **What changes:** Preserves and formalizes the existing `Store` implementation in [`store.py`](../../src/campus_assistant/store.py).
- **Existing data:** Current SQLite tables `items`, `item_history`, and `changes` are 100% compliant with this specification.

---

## 12. Acceptance criteria

| ID | Given | When | Then | Test level |
|---|---|---|---|---|
| **AC-1** | A new item with unique ID | Upserted into store | Item row is created, `change: "created"` is logged, and no rows added to `item_history` (FR-5) | unit |
| **AC-2** | An existing item whose `due_at` has changed | Upserted into store | Previous version saved to `item_history`, `updated_at` updated, and `changes` logs `change: "updated"`, `fields: ["due_at"]` (FR-1, FR-4) | unit |
| **AC-3** | An item upserted with identical content but updated `meta.eml_path` | Upserted into store | Return status is `"unchanged"`, `last_seen` updated, zero rows in `item_history` (FR-2) | unit |
| **AC-4** | A source completes a full fetch missing item X | `mark_missing()` is called | Item X has `deleted_at` populated and `changes` logs `change: "removed"` (FR-5) | unit |
| **AC-5** | A soft-deleted item is fetched again by the source | Upserted into store | Item X has `deleted_at = NULL` and `changes` logs `change: "restored"` (FR-5) | unit |

---

## 13. Open questions and decisions

| ID | Question | Owner | Resolution | Date |
|---|---|---|---|---|
| **Q-1** | Should `item_history` snapshots be compressed (e.g. gzip/zstandard) in SQLite? | spiralsky | **Resolved**: Uncompressed JSON for v1; SQLite file sizes are small enough (~10-50MB) that compression complexity is unnecessary. | 2026-10-27 |

---

## 14. Change log

| Date | Change | By |
|---|---|---|
| 2026-10-27 | Initial authoring of change tracking and history specification formalizing store.py behaviour and retention rules. | spiralsky & Assistant |

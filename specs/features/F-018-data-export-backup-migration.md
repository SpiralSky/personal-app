# Data export, backup and migration

> **Specification state.** Draft establishing complete backup, restore, user data export, schema migration engine, snapshot management, and retention policies.

| Field | Value |
|---|---|
| ID | F-018 |
| Status | Draft |
| Owner | spiralsky |
| Created | 2026-10-27 |
| Last updated | 2026-10-27 |
| Target release | v1.0 |
| Related architecture | Product Scope ([`F-001`](F-001-product-scope-surfaces.md)), Canonical Taxonomy ([`F-002`](F-002-canonical-item-taxonomy.md)), Change Tracking ([`F-003`](F-003-change-tracking-history.md)), Local API Contract ([`F-015`](F-015-local-api-contract-security.md)), CLI Operations ([`F-016`](F-016-cli-service-operations.md)) |
| Supersedes | — |
| Superseded by | — |

**Source key.** `owner` = confirmed by product owner; `baseline` = observed in current implementation; `proposal` = proposed specification.

---

## 1. Summary

This specification defines the disaster recovery, portable data export, and schema evolution mechanisms for `campus-assistant`.

The system distinguishes strictly between two workflows:
1. **Backups (System Snapshot & Disaster Recovery):** Self-contained, timestamped archives (`.tar.gz`) stored in the application data directory. Backups contain the complete SQLite database snapshot (captured cleanly via SQLite online backup API / WAL checkpointing) and all non-sensitive file storage (attachments, cached task documents, generated study briefs). **Sensitive credentials, tokens, session cookies, and API keys are strictly excluded.** Backups run automatically on a configurable daily schedule (defaulting to retaining the last 7 daily snapshots), can be triggered manually at any time via Settings or the CLI, and can be inspected, restored, or deleted.
2. **Exports (Portable Data Sovereignty):** User-facing portable ZIP archives containing standardized, human- and machine-readable exports: structured metadata in `items.jsonl`, full study plans in `briefs/`, iCalendar schedules in `calendar.ics`, and exported attachments in `attachments/`.
3. **Migration Engine:** A lightweight, zero-dependency schema migration engine utilizing SQLite `PRAGMA user_version` and atomic transactions. Every automated schema migration automatically triggers a pre-migration safety backup before applying incremental DDL/DML scripts.

---

## 2. Problem and context

The initial implementation in `store.py` instantiated database tables using static `CREATE TABLE IF NOT EXISTS` statements:
* **No Schema Versioning:** As new features are introduced (e.g., triage labels, confidence scores, FTS5 full-text indexing, crawler references), there was no mechanism to alter tables, add indexes, or run schema transformations. Updating the code on an existing user database risked crashes or silent data drift.
* **Lack of Disaster Recovery:** Without an integrated backup mechanism, database corruption, accidental deletions, or disk failures meant complete loss of history, triage decisions, and generated task briefs.
* **Concurrency and File Locking:** Taking a raw file copy of an active SQLite database in WAL mode while background sync workers or web requests are active produces corrupted or truncated database snapshots.
* **No Clean Export Path:** Users had no mechanism to export their notes, academic tasks, and briefs into an interoperable format for archiving or migration to external tools.

`F-018` establishes deterministic snapshot creation, concurrency management, backup retention, portable exports, and a transactional schema migration pipeline.

---

## 3. Users and jobs

| User | Job / need | Notes |
|---|---|---|
| Student / User | Peace of mind that academic data, notes, and task history are safe against corruption or accidental loss. | `owner` Automated background backups running silently with zero manual maintenance required. |
| Student / User | Configure backup schedule and retention, create manual backups, or restore previous points from Settings. | `owner` Web UI control panel with simple "Create Backup", "Restore", and "Delete" actions. |
| Student / User | Export all academic tasks, study briefs, and calendars to standard open formats (JSONL, Markdown, ICS). | `owner` Portable ZIP export ensuring data ownership and tool interoperability. |
| Developer / App Upgrade | Evolve database schema, table structures, and data backfills safely across application releases. | `proposal` Transactional schema migrations with automatic pre-migration recovery snapshots. |
| CLI / Script User | Automate backups, inspect archive integrity, trigger restores, or run migrations headlessly. | `owner` Dedicated CLI commands matching REST API endpoints. |

---

## 4. Goals and non-goals

**Goals**
- **G-1 (Strict Exclusion of Sensitive Data):** Backups and exports must never include plain-text API keys, OAuth tokens, session cookies, master passwords, or OS keyring secrets. `owner`
- **G-2 (Safe Backup Concurrency):** Database backups must be captured using SQLite's online backup API (`sqlite3_backup`) or `VACUUM INTO`, ensuring clean point-in-time consistency even while read/write transactions are active. `proposal`
- **G-3 (Automated Scheduling & Retention):** Configurable automated backups defaulting to daily execution with a default retention policy of the last 7 daily backups. `owner`
- **G-4 (Settings & Web UI Management):** Full backup management inside the Web UI Settings panel: view list, see sizes/dates, trigger on-demand backup, restore, or delete old backups. `owner`
- **G-5 (Safe Restoration with Concurrency Lock):** During a restore, the daemon enters an exclusive maintenance mode (pausing sync tasks and rejecting concurrent mutations), takes an automatic safety rollback checkpoint (`pre_restore_<timestamp>.tar.gz`), unpacks the archive, verifies database integrity, and resumes operations. `proposal`
- **G-6 (Portable ZIP Export):** Provide a user-facing export packaged as a ZIP containing `items.jsonl`, `calendar.ics`, Markdown briefs, and attachments. `owner`
- **G-7 (Zero-Dependency Migration Engine):** An embedded migration runner using SQLite `PRAGMA user_version` that executes ordered, transactional SQL and Python migrations sequentially. `proposal`
- **G-8 (CLI Parity):** All backup, export, restore, and migration operations must be fully supported via headless CLI commands (`campus backup ...`, `campus export`, `campus migrate`). `owner`

**Non-goals**
- **NG-1 (Cloud Storage Synchronization):** Automatic uploading of backup archives to cloud providers (Google Drive, Dropbox, AWS S3) is out of scope. Backups reside in the standard local data directory.
- **NG-2 (Encrypted Backup Archives):** Since backups strictly exclude secrets and credentials, backup archives are unencrypted standard compressed tarballs (`.tar.gz`). Filesystem encryption (e.g. LUKS/fscrypt) handles machine-level security.
- **NG-3 (Alternative Backup Locations):** Backups are stored in `~/.local/share/campus-assistant/backups/`. Custom paths across external disks are deferred.
- **NG-4 (Arbitrary Schema Downgrades / Reversible DDL):** Schema migrations are forward-only. Downgrading application versions requires restoring from an earlier pre-migration backup.

---

## 5. Current behaviour (baseline)

1. **Database Schema:** Defined statically in `src/campus_assistant/store.py` with `CREATE TABLE IF NOT EXISTS`. No `PRAGMA user_version` is tracked.
2. **Backups:** None. No CLI command or scheduled task exists.
3. **Data Export:** Only an iCalendar feed exists at `/calendar.ics`. Items and task briefs cannot be exported in bulk.
4. **Restore:** None. Replacing database requires manual file manipulation.

---

## 6. Desired behaviour

### 6.1 Backup Creation Workflow
1. **Trigger:** Backups are triggered either automatically by the daemon scheduler (e.g. daily at 03:00 local time), manually by the user via the Settings UI ("Create Backup Now"), before a schema migration, or via `campus backup create`.
2. **Online Database Snapshot:** The engine executes SQLite `VACUUM INTO '<temp_dir>/campus.db'` (or uses standard `sqlite3.Connection.backup()`). This creates an atomic, non-corrupted database file without locking reads or failing due to active WAL files.
3. **Attachment Aggregation:** The non-sensitive file tree (`documents/`, `attachments/`) is gathered into the temporary directory. Sensitive credential stores (e.g., `.keyring`, `.session.json`, auth tokens) are omitted.
4. **Metadata Manifest:** A `manifest.json` is generated containing metadata:
   - `version`: Backup format version (`1`).
   - `created_at`: ISO 8601 UTC timestamp.
   - `schema_version`: SQLite `PRAGMA user_version`.
   - `app_version`: Current `campus-assistant` software release.
   - `db_size_bytes`: Database size.
   - `attachment_count`: Total count of archived files.
   - `sha256_checksum`: SHA-256 hash of the SQLite database.
5. **Archive Packaging:** Files are compressed into a single archive:
   `~/.local/share/campus-assistant/backups/backup_YYYYMMDD_HHMMSS.tar.gz`
6. **Retention Pruning:** The retention manager inspects existing backups in the backup directory, orders them chronologically, and prunes archives exceeding the configured limit (default: 7 backups).

### 6.2 Restore Workflow and Concurrency Control
1. **Initiation:** The user runs `campus backup restore <filename>` or selects "Restore" in Settings.
2. **Maintenance Mode Lock:**
   - If running inside or against the daemon, the daemon transitions into `MAINTENANCE` state.
   - Active sync jobs (e.g. Brightspace crawler or email ingestion) are requested to pause/cancel.
   - Incoming non-administrative HTTP requests receive `503 Service Unavailable (System in Maintenance / Restore)`.
3. **Verification:** The archive is unpacked to a staging directory. The manifest and SHA-256 checksums are verified. SQLite `PRAGMA integrity_check` is executed on the restored database.
4. **Safety Rollback Snapshot:** Before altering live files, the current live state is automatically backed up to:
   `~/.local/share/campus-assistant/backups/pre_restore_YYYYMMDD_HHMMSS.tar.gz`
5. **File Replacement & Reconnect:**
   - The live SQLite database connection pool is closed.
   - The live database and attachment folders are replaced with the restored files.
   - Connection pools are re-established.
   - If schema version is behind the current code, the migration engine automatically runs pending migrations.
6. **Maintenance Mode Release:** The daemon exits maintenance mode, re-enables normal REST endpoints, and resumes scheduling.

### 6.3 Portable Export Workflow
1. The user requests an export via the Settings page or `campus export --output export.zip`.
2. An ephemeral ZIP archive is assembled with a clean, portable layout:
   ```text
   export_YYYYMMDD/
   ├── manifest.json         # Export date, counts, app version
   ├── items.jsonl           # All canonical items (one JSON object per line)
   ├── items.csv             # Tabular summary (id, source, kind, title, due_at, course_name)
   ├── calendar.ics          # Full iCalendar export of all deadlines and events
   ├── briefs/               # Generated task briefs in Markdown (*.md)
   │   └── <item-id>_<title>.md
   └── attachments/          # Associated files and document cache
       └── <item-id>/
   ```
3. The archive is streamed to the user via HTTP download or written to the local target path.

### 6.4 Schema Migration Engine
1. **Runner Initialization:** On application startup (or CLI command `campus migrate`), the engine connects to SQLite and queries:
   `PRAGMA user_version;`
2. **Migration Registry:** The engine reads versioned migration scripts located in `src/campus_assistant/migrations/`:
   - `0001_initial_schema.sql`
   - `0002_add_triage_columns.sql`
   - `0003_fts5_virtual_tables.sql`
   - `0004_backfill_item_normalizations.py`
3. **Execution Plan:** If current `user_version < TARGET_VERSION`:
   a. **Pre-Migration Snapshot:** Creates an automatic snapshot `backup_pre_migration_v{user_version}_{timestamp}.tar.gz`.
   b. **Transaction Execution:** For each pending migration step:
      - Starts immediate transaction (`BEGIN IMMEDIATE`).
      - Applies SQL or executes the Python step.
      - Increments `PRAGMA user_version = step_version`.
      - Commits transaction (`COMMIT`).
   c. **Failure Handling:** If any step raises an error, the transaction rolls back (`ROLLBACK`). The engine halts startup, alerts the user, and leaves previous data intact.

---

## 7. Functional rules

| ID | Rule |
|---|---|
| FR-1 | **Strict Secret Omission:** Backup and export archives must strictly exclude credentials, secrets, auth tokens, passwords, and `.session.json` state files. `owner` |
| FR-2 | **Atomic DB Snapshots:** Database backups must never perform raw file copies of active `.db` files. Snapshots must use SQLite's backup API or `VACUUM INTO` to guarantee WAL-safe, consistent snapshots. `proposal` |
| FR-3 | **Default Backup Schedule:** Automated backups run once per day (default 03:00 local time). This schedule is configurable in Settings. `owner` |
| FR-4 | **Default Retention Limit:** The system retains the last 7 daily backups by default. When a new automated backup succeeds, older backups beyond the retention limit are automatically deleted. `owner` |
| FR-5 | **On-Demand Manual Backups:** Users can trigger a manual backup at any time via Settings UI or CLI (`campus backup create`). Manual backups are subject to retention or can be flagged as pinned. `owner` |
| FR-6 | **Settings Backup Management:** The Settings UI provides an interactive management list displaying backup timestamps, archive file sizes, manifest metadata, and one-click actions: "Download", "Restore", and "Delete". `owner` |
| FR-7 | **Pre-Restore Rollback Snapshot:** Prior to overwriting the database or attachments during a restore, a safety checkpoint (`pre_restore_<timestamp>.tar.gz`) must be created automatically. `proposal` |
| FR-8 | **Restore Concurrency Lock:** During restore execution, background worker tasks must be paused and incoming mutation requests must be rejected with HTTP 503 until restore completes. `proposal` |
| FR-9 | **Integrity Verification:** Restored databases must pass `PRAGMA integrity_check` before being swapped into production. Corrupted archives must abort without affecting live data. `proposal` |
| FR-10 | **Portable ZIP Export Layout:** Data exports must be packaged as standard `.zip` files containing `manifest.json`, `items.jsonl`, `calendar.ics`, markdown `briefs/`, and course `attachments/`. `owner` |
| FR-11 | **PRAGMA user_version Migration Tracking:** Database schema version is tracked strictly via SQLite `PRAGMA user_version`. Migrations are applied in strict ascending integer sequence. `proposal` |
| FR-12 | **Pre-Migration Safety Backup:** Any automated or manual migration execution that modifies `user_version` must first create a pre-migration backup snapshot. `proposal` |
| FR-13 | **Transaction Isolation for Migrations:** Each migration script executes within an explicit transaction (`BEGIN IMMEDIATE`). On failure, changes are rolled back completely. `proposal` |
| FR-14 | **CLI and API Parity:** Every backup, export, restore, and migration capability must be accessible both via REST API endpoints and CLI commands. `owner` |

---

## 8. Data and contracts

### 8.1 Configuration Settings (`config.py` / `settings.json`)

```json
{
  "backup": {
    "enabled": true,
    "schedule_cron": "0 3 * * *",
    "retention_count": 7,
    "include_attachments": true
  }
}
```

### 8.2 Backup Manifest Format (`manifest.json`)

```json
{
  "manifest_version": 1,
  "app_version": "1.0.0",
  "created_at": "2026-10-27T03:00:00Z",
  "backup_type": "scheduled",
  "schema_version": 4,
  "database": {
    "filename": "campus.db",
    "size_bytes": 14589952,
    "sha256": "3a7b1c4e9f...64hex"
  },
  "attachments": {
    "count": 42,
    "total_size_bytes": 314572800
  }
}
```

### 8.3 REST API Endpoints

Mounted under `/api/v1/system/`:

| Method | Path | Request Body | Response Body | Description |
|---|---|---|---|---|
| `GET` | `/api/v1/system/backup/config` | — | `BackupConfig` | Get backup schedule and retention settings. |
| `PATCH` | `/api/v1/system/backup/config` | `BackupConfigUpdate` | `BackupConfig` | Update schedule, retention count, or toggle enabled. |
| `GET` | `/api/v1/system/backups` | — | `list[BackupInfo]` | List available backups with size, timestamp, metadata. |
| `POST` | `/api/v1/system/backups` | `{}` | `BackupInfo` | Trigger an immediate manual backup snapshot. |
| `GET` | `/api/v1/system/backups/{id}/download` | — | `binary (.tar.gz)` | Download backup archive file. |
| `DELETE` | `/api/v1/system/backups/{id}` | — | `{"deleted": true}` | Delete a specific backup archive. |
| `POST` | `/api/v1/system/backups/{id}/restore` | `{}` | `{"status": "restored", ...}` | Restore system from the specified backup archive. |
| `POST` | `/api/v1/system/export` | `ExportOptions` | `binary (.zip)` | Generate and download portable data export. |
| `GET` | `/api/v1/system/migrations` | — | `MigrationStatus` | Get current `user_version` and available migrations. |
| `POST` | `/api/v1/system/migrations/apply` | `{}` | `MigrationResult` | Run pending schema migrations. |

### 8.4 CLI Commands (`campus`)

| Command | Arguments / Flags | Description |
|---|---|---|
| `campus backup create` | `[--name <str>] [--no-attachments]` | Create a new backup snapshot immediately. |
| `campus backup list` | `[--json]` | Display list of existing backups, sizes, and dates. |
| `campus backup restore` | `<archive-name-or-path> [--yes]` | Restore system from a backup archive. Prompts confirmation. |
| `campus backup delete` | `<archive-name> [--yes]` | Delete a specific backup archive. |
| `campus backup prune` | `[--keep <N>]` | Manually prune backups according to retention policy. |
| `campus export` | `[--output <path.zip>]` | Generate portable data export ZIP. |
| `campus migrate status` | — | Display current database schema version and pending scripts. |
| `campus migrate apply` | `[--target <N>]` | Run pending database migrations with pre-migration backup. |

---

## 9. Failure modes and resiliency

| Failure Mode | Impact | Resiliency Behavior |
|---|---|---|
| Disk space exhausted during backup | Backup fails; corrupted partial archive left on disk. | Backup creates files in temporary directory first (`.tmp`); on disk error, temporary files are removed. Failed backup does not displace existing retained backups. User/log is notified. |
| Backup corrupted during restore attempt | System could be left in unbootable or partial state. | Manifest check and `PRAGMA integrity_check` are run in staging directory *before* touching live data. Live state is backed up to `pre_restore_*.tar.gz`. If restore fails, original database is preserved. |
| Power failure or crash mid-migration | Schema half-migrated; tables inconsistent. | Every migration step is wrapped in `BEGIN IMMEDIATE ... COMMIT`. If interrupted, SQLite rolls back the transaction. Pre-migration backup exists on disk for instant recovery. |
| Scheduled backup runs during intense crawler sync | DB contention or timeout. | SQLite online backup API (`VACUUM INTO` / backup API) operates without blocking active readers and waits gracefully for lock windows without aborting active crawler transactions. |

---

## 10. Security and privacy

1. **Exclusion of Credentials:** Plaintext secrets, master passwords, OAuth refresh tokens, session cookies (`.session.json`), and keyring files are strictly skipped during both backup and export archive generation.
2. **Local Loopback Security:** All REST endpoints under `/api/v1/system/` enforce local loopback binding (`127.0.0.1`), Host/Origin header validation, and CSRF protection as defined in `F-015`.
3. **Directory Traversal Defense:** Backup identifiers and restore filenames are sanitized to prevent directory traversal (`../`) attacks when accessing archives in `~/.local/share/campus-assistant/backups/`.

---

## 11. Compatibility and migration

- **Schema Evolution:** Existing databases without `PRAGMA user_version` (value `0`) will be inspected by migration step `0001_initial_schema.sql`. Since tables already exist with `CREATE TABLE IF NOT EXISTS`, the step will safely stamp `PRAGMA user_version = 1` without data loss.
- **Frontend Settings UI:** Settings page in the Web UI (`Settings.tsx`) gains a dedicated **"Data & Backups"** tab for backup schedules, retention limits, manual snapshot creation, export download, and backup restoration.

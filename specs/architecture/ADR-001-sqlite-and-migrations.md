# SQLite as the persistence engine, with forward-only migrations

| Field | Value |
|---|---|
| ID | ADR-001 |
| Status | accepted |
| Date | 2026-10-28 |
| Affects | F-002, F-003, F-005, F-006, F-007, F-013, F-018, F-019 |
| Supersedes | — |

## Context

The product is a single-user, local-first daemon. All authoritative data is
private academic content (items, bodies, attachments, labels, LLM analyses,
audit records). It must be queryable offline, searchable (FTS5), backed up as a
portable artefact, and never depend on a cloud service (F-001 NG-1).

Several feature specs already describe SQLite tables, PRAGMAs and migration
behaviour (`F-003` §8.1, `F-006` §8.2, `F-018` §6, `F-019` §8). The crawler is a
separate service (`ADR-002`) with its own schema. Storing the schema in feature
prose has already produced drift, so the canonical schema lives in
[A-001](A-001-runtime-contracts-persistence.md) §7 and this record fixes the
storage and migration mechanics.

## Decision

1. **Two SQLite databases, one per service.** `campus-assistant.db` (main app)
   and `crawler.db` (crawler). They are never `ATTACH`ed to each other and no
   cross-database foreign keys exist; cross-service references use IDs only.
2. **One file per database**, WAL journal mode, `foreign_keys = ON`,
   `synchronous = NORMAL`, `busy_timeout = 10000` for writers. Readers may use
   separate connections; the WAL allows concurrent reads during writes.
3. **Timestamps** are stored as UTC ISO-8601 text (`YYYY-MM-DDTHH:MM:SSZ`) and
   JSON payloads as `TEXT` (never SQLite `JSON1`-typed columns), so a database
   dump is readable and portable without the app.
4. **Schema version** is `PRAGMA user_version`, bumped once per migration.
   Migrations are numbered, forward-only Python modules applied inside a single
   transaction at startup; a failed migration rolls back and the daemon refuses
   to start. There is no down-migration path.
5. **Backup before migrate.** Before applying any migration, take a
   `VACUUM INTO` snapshot into the backups directory (F-018). Rollback is
   "restore the pre-migration snapshot", not a reverse migration.
6. **No ORM-owned schema.** The schema is expressed as SQL executed by the
   migration runner; the Python layer maps rows explicitly. This keeps DDL
   reviewable and identical to A-001 §7.
7. **FTS5** (main app item search, crawler search) is built as external-content
   or contentless FTS5 virtual tables maintained inside the same transaction as
   the row write, so index and data cannot diverge.

## Alternatives considered

- **PostgreSQL / a server database:** rejected — violates the single-binary,
  offline-first, zero-service constraint (F-001 NG-1/NG-2) and makes backup and
  restore heavier than a file copy.
- **DuckDB or an embedded document store:** rejected — the access pattern is
  transactional upsert plus relational filters and FTS, which SQLite already
  serves, and it would discard the schemas already specified by F-003/F-006/F-019.
- **ORM-managed migrations (Alembic/SQLAlchemy):** rejected for v1 as
  unnecessary weight and an abstraction that hides the DDL A-001 must own; a
  ~100-line numbered runner is enough and is testable.
- **Down migrations:** rejected — no production rollback story is needed for a
  local app whose rollback is a snapshot restore; maintaining inverse
  migrations doubles the surface with little benefit.

## Consequences

- A single database file remains the unit of backup/export (F-018).
- Long-running reads must not hold a write transaction; the FTS index update is
  part of the write transaction, so a slow write briefly blocks other writers.
- Because there are no cross-database joins, the main app must fetch crawler
  items over HTTP and cache them; the boundary is enforced by construction.
- Restoring an older snapshot is the only rollback, so the pre-migration
  snapshot must be verified (`PRAGMA integrity_check`) before being trusted.
- Any future migration must be additive or use table-rebuild; destructive
  changes require a documented data-loss note in F-018.

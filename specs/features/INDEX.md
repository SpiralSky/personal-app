# Feature index

Registry of feature specs. **Status is authoritative only when a file exists and has been reviewed.** Candidate rows are placeholders to make the scope visible; they are not requirements.

## Status overview

| Status | Count |
|---|---:|
| Accepted | 3 |
| In review | 1 |
| Draft | 8 |
| Baseline (needs spec) | 7 |
| Superseded | 0 |

## Candidate features

| ID | Feature | Status | Priority | Current surface | Notes / questions the spec must answer |
|---|---|---|---|---|---|
| F-001 | [Product scope and supported surfaces](F-001-product-scope-surfaces.md) | Accepted | High | Web, CLI, KDE tray, Plasma widget | Single-user loopback architecture, surface tiers (Tier 1 Web/CLI/MCP vs Tier 2 KDE/iCal), headless runtime, and explicit non-goals |
| F-002 | [Canonical item and source taxonomy](F-002-canonical-item-taxonomy.md) | Accepted | High | `models.py`, `brightspace/normalize.py`, `mail.py` | Universal Item model, hierarchical source taxonomy, kind definitions, identity construction, and UTC date normalization |
| F-003 | [Change tracking and history](F-003-change-tracking-history.md) | Draft | High | `store.py` | Content-hash change detection, historical version snapshots (`item_history`), field-level diff logs (`changes`), and soft-deletion |
| F-004 | [Brightspace sync and crawler integration](F-004-automatic-brightspace-sync.md) | Accepted | High | `brightspace/`, `runner.py`, Sources/Settings | Integration with standalone F-019 crawler daemon over REST API; on-demand item referencing without database duplication; proxying sync triggers and mutations |
| F-005 | [Email ingestion and archive import](F-005-email-ingestion.md) | Draft | High | `mail.py`, `/ingest/email` | Multi-source email ingestion (Prospect Mail, Thunderbird, direct IMAP/Graph); strict account isolation; 25 MB content-addressed attachment blobs |
| F-006 | [Triage cascade and review workflow](F-006-triage-cascade-workflow.md) | Draft | High | `analysis/`, `llm/`, `Inbox.tsx` | Multi-tiered cascade (rules → logprob classifier → LLM extraction), execution budgets, confidence cutoffs, review queue, and calibration loop |
| F-007 | [Task briefs and study planning](F-007-task-briefs-study-planning.md) | Draft | High | `analysis/pipeline.py`, `Tasks.tsx` | Automated course file matching & ranking, document text extraction cache, grounded brief extraction, study timelines, calendar sync, and interactive MCP mutation |
| F-008 | Web information architecture and navigation | Baseline | Medium | `App.tsx`, `Sidebar.tsx` | Consolidate Today/Inbox/Tasks/Browse/Sources/System/Settings? Navigation model? |
| F-009 | Inbox labelling and keyboard workflow | Baseline | High | `Inbox.tsx` | Filters, selection, shortcuts, optimistic updates, note handling, accessibility |
| F-010 | Task and deadline views | Baseline | Medium | `Today.tsx`, `Tasks.tsx`, `/upcoming` | What is “due”? Overdue handling? Submitted tasks? Calendar vs list? |
| F-011 | Search, filters and pagination | Baseline | Medium | `/items`, `Browse.tsx`, `/triage` | Query semantics, prefix matching, total counts, FTS, empty states |
| F-012 | Calendar feed and notifications | Baseline | Medium | `ics.py`, `/calendar.ics`, KDE notify | Feed window, UID stability, alarms, desktop notification rules, dedupe |
| F-013 | [LLM provider configuration, privacy, and MCP](F-013-llm-provider-privacy-mcp.md) | Draft | High | `/settings/llm`, `Settings.tsx`, `llm/` | Multi-provider adapters (Claude, OpenAI, Gemini, Local), OS keyring & encrypted vault, dual-transport MCP (stdio + SSE), and anonymization layer |
| F-014 | System status, errors and diagnostics | Baseline | Medium | `System.tsx`, `Errors.tsx`, `/status`, `/errors` | Persisted errors? Log levels? Health checks? What is safe to expose? |
| F-015 | [Local API contract and security](F-015-local-api-contract-security.md) | Draft | High | `api.py` | Versioned REST API (`/api/v1`), standard data/error envelopes, loopback binding, and Origin/Host security checks |
| F-016 | [CLI and background service operations](F-016-cli-service-operations.md) | Draft | Medium | `cli.py`, `service.py` | Dual-mode execution (daemon HTTP proxy vs offline in-process), systemd user service management, signal handling, and JSON outputs |
| F-017 | Desktop integration (KDE tray/plasmoid) | Baseline | Low | `kde/` | Keep, rebuild on the contract, or drop? Packaging and dependency story |
| F-018 | [Data export, backup and migration](F-018-data-export-backup-migration.md) | Draft | High | SQLite + files, Settings, CLI | Export format, restore, schema migration, rollback, retention |
| F-019 | [Brightspace crawler](F-019-brightspace-crawler.md) | In review | High | Standalone crawler service & submodule | Standalone portable daemon & CLI; L3 academic coverage (including Discussions, Surveys, Checklists); dual REST API + MCP server; FTS5 indexing with document text extraction; safe tiered mutations (notifications, discussion posts) with audit log |

## Recommended first specs

If the rewrite is approached in vertical slices, the highest-information specs are:

1. **F-002 — Canonical item and source taxonomy.** Everything else depends on this contract.
2. **F-003 — Change tracking and history.** The current design is good but implicit; freeze it before replacing storage.
3. **F-006 — Triage cascade and review workflow.** This is the product’s differentiating logic and the easiest place to lose behaviour silently.
4. **F-015 — Local API contract and security.** Contract-first design prevents a repeat of the current client drift.

**F-019 (Brightspace crawler)** is being authored first as the data-plane slice: a standalone crawler and programmatic API. It feeds the other ingestion-dependent features, including F-004 (Automatic Brightspace sync), which remains an empty owner-authored scaffold for the scheduling/sync feature ([file](F-004-automatic-brightspace-sync.md)). The owner will author F-004 in a later session.

## Adding a spec

1. Pick the next free `F-NNN`.
2. Copy [TEMPLATE.md](TEMPLATE.md) to `F-NNN-<slug>.md`.
3. Change status from `Baseline` to `Draft` here.
4. Link the file in the table.
5. Update the status overview counts.

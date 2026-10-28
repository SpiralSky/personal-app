# The Brightspace crawler is a separate distributable service

| Field | Value |
|---|---|
| ID | ADR-002 |
| Status | accepted |
| Date | 2026-10-28 |
| Affects | F-004, F-019, F-016, F-018 |
| Supersedes | — |

## Context

Brightspace ingestion used to live inside `campus-assistant` as
`campus_assistant/brightspace/`, writing directly into the monolith's SQLite
schema (`F-019` §2). That coupled Playwright session handling, scraping and the
product's item model in one process: a crawler crash could take down the UI, a
schema change for one item kind could break sync, and agents had no way to read
crawled courses without going through the product.

`F-019` §5 specifies a standalone crawler daemon with its own data directory,
schema, REST `/v1` API and MCP server. `F-019` Q-4 left the packaging story open
(standalone package vs. submodule vs. in-process module). `F-004` (Accepted)
assumes the crawler is a separate loopback service it proxies to.

## Decision

1. **Separate distributable package.** The crawler is its own Python
   distribution (`campus-crawler`) with its own `pyproject.toml`, pinned
   dependencies, lockfile and console scripts (`campus-crawler serve|mcp|auth|sync|search`).
   It is not a submodule of the main app and does not import from
   `campus_assistant`.
2. **Separate process and lifecycle.** It runs as its own `systemd --user` unit
   (`campus-crawler.service`) with its own data directory
   (`~/.local/share/campus-crawler`, override `CRAWLER_DATA_DIR`), logs and
   Playwright session profiles. Stopping or crashing it must not affect the main
   daemon or web UI.
3. **Separate database.** It owns `crawler.db` and its blob store, and never
   writes `campus-assistant.db` (see ADR-001).
4. **Loopback contract only.** The main app integrates through the crawler's
   versioned REST API on `127.0.0.1` (`/v1/...`, F-019 §9.1) and, for agents,
   through its MCP server. No shared filesystem state, no direct SQLite access.
5. **Main app is a proxy, not a second crawler.** `campus-assistant` exposes
   `/api/v1/sources/brightspace/*` (F-004 §8.1) which proxies triggers,
   status/login and mutation endpoints to the crawler, tracks `job_id`s, and
   maps crawler failures to its own error envelope (`crawler_unavailable` 503,
   `crawler_auth_required` 401 per F-015).
6. **Two independently versioned APIs.** The crawler's `/v1` is frozen against
   F-019's acceptance criteria before F-004 implementation starts; the main
   app's `/api/v1` is a distinct contract (F-015/A-001 §6).
7. **Shared item model is a contract, not a code dependency.** The crawler emits
   its own item shape; F-004's adapter maps it onto the canonical `Item`
   contract (F-002). Both sides may evolve independently as long as the mapping
   is tested.

## Alternatives considered

- **In-process module (current design):** rejected — keeps the crash and lock
  coupling, forces Playwright into the daemon's dependency set and violates the
  separation F-019's contract relies on.
- **Git submodule of the main repo:** rejected — a submodule has no independent
  release or install path, so the "portable crawler for scripts and agents"
  use case in F-019 §1 cannot be served without cloning the product.
- **Crawler as a plugin loaded by the main app at runtime:** rejected — still
  shares a process, event loop and dependency resolution.

## Consequences

- Two installs, two units, two upgrade paths; `campus` CLI must report crawler
  presence and health rather than assume it.
- The main app cannot use SQL joins against crawled data; it caches or queries
  over HTTP, so some list views pay a latency cost that must be bounded by
  timeouts and explicit `crawler_unavailable` handling.
- Cross-schema change of the emitted item shape requires a coordinated release
  plus an adapter test; this is the cost of the boundary.
- Backup/export (F-018) must treat the two data directories as two units and
  document that crawler data is re-derivable (re-crawlable) while the main
  database is not.

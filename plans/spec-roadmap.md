# Spec execution roadmap

Sequential plan. Work top to bottom; do not start a spec until its
prerequisites are `Accepted` (or `Implementing`). Read
[README.md](README.md) for the autonomy policy first.

Status legend follows `specs/README.md`:
`Baseline → Draft → In review → Accepted → Implementing → Implemented`.

Last audited: 2026-10-28. Re-audit status from file metadata before starting
each phase — INDEX is known to be stale.

## Inventory and real status

| ID | Spec | File status | INDEX says | Role |
|---|---|---|---|---|
| F-001 | Product scope and surfaces | **Completed** (invalid value) | Draft | Scope, surfaces, RBAC, process model |
| F-002 | Canonical item taxonomy | Accepted | Accepted | Domain contract root |
| F-003 | Change tracking and history | Draft | Draft | Storage/change contract |
| F-004 | Brightspace sync integration | **Accepted** | Accepted | Crawler consumer (was "empty scaffold" — see Gate 0) |
| F-005 | Email ingestion | Draft | Draft | Ingestion |
| F-006 | Triage cascade | Draft | Draft | Differentiating logic |
| F-007 | Task briefs and planning | Draft | Draft | LLM output surface |
| F-008–F-012, F-014, F-017 | Web IA, inbox, tasks, search, calendar, diagnostics, desktop | Baseline | Baseline | No files yet; author later |
| F-013 | LLM provider, privacy, MCP | Draft | Draft | Intelligence substrate |
| F-015 | Local API contract and security | Draft | Draft | System contract |
| F-016 | CLI and service operations | Draft | Draft | Operations |
| F-018 | Export, backup, migration | Draft (**no ACs**) | Draft | Last, depends on everything |
| F-019 | Brightspace crawler | In review | In review | Independent data plane |

## Phase 0 — corpus baseline and architecture layer (agent-only, except G0-Q1)

Do this once, before feature work.

- [x] **G0-1 Commit the corpus.** Branch `docs/spec-baseline` off `master`;
      commit `specs/`, `plans/`, `CLAUDE.md`, `docs/` as-is. Merge after review.
      This gives every later status change a diffable baseline.
      _(done: 95b9533; awaiting merge)_
- [x] **G0-2 Reconcile INDEX.** Recompute status counts from file metadata, fix
      stale F-004 prose (`INDEX.md:48` still calls it an empty scaffold), link
      every existing spec.
      _(counts recomputed: Accepted 3 / In review 1 / Draft 8 / Baseline 7;
      F-001 row corrected. The F-004 prose is **left unchanged** because it is
      the subject of G0-Q1 — do not pre-empt that answer.)_
- [x] **G0-3 Normalise statuses.** F-001 `Completed` → `Accepted` (it defines
      scope and has FRs/ACs). Add F-001 missing edge-case/failure-mode and
      open-question sections as empty scaffolds, not invented content.
      _(also added an empty compatibility/migration scaffold, which the
      acceptance gate requires; change log notes the normalisation.)_
- [x] **G0-4 Decide and write the architecture layer** (see "Design
      assessment" below):
      - [x] `specs/architecture/A-001-runtime-contracts-persistence.md` — the
            16 required sections from `specs/architecture/README.md`, at
            baseline depth. Extract, do not invent: systemd/CLI dispatch from
            F-001 §8; DDL from F-003/F-006/F-019; API envelope/security from
            F-015 §6; provider/config shapes from F-013 §5–7; deployment from
            F-019 §5.
      - [x] `ADR-001-sqlite-and-migrations.md`
      - [x] `ADR-002-crawler-as-separate-service.md` (resolves F-019 Q-4
            packaging disjunction: choose a packaging story and state it)
            _(standalone `campus-crawler` distribution, own unit/data dir/DB.)_
      - [x] `ADR-003-local-api-security-model.md` (reconciles F-015's
            loopback/Origin rules, F-016's daemon token, F-013's MCP auth)
            _(F-001's RBAC is authoritative; F-015 NG-1 must be amended before
            F-015 is accepted.)_
- [x] **G0-5 Cross-spec contract reconciliation.** Fix drift in the specs, or
      record it as an ADR:
      - F-016 AC-016-01 calls `POST /api/v1/sync/run`; F-015 lists
        `/api/v1/brightspace/sync`, F-004 defines its own trigger route.
        _(resolved: A-001 §6.2 canonicalises `/api/v1/sources/brightspace/*`,
        aliases the other two; AD-20261028-04.)_
      - F-016 introduces `.daemon-token` bearer auth; F-015 NG-1 says "no
        auth". Pick one model in ADR-003. _(done — ADR-003.)_
      - F-003 §6.1 / FR-6/7 reference an `analyses` table that no spec
        defines; define it in A-001 §7.
        _(done — A-001 §7.2; AD-20261028-06.)_
      - F-019 has no compatibility/migration section despite decoupling from
        `campus-assistant/brightspace/`.
        _(deferred to Phase 2 step 5, where the section is authored; it is a
        Draft spec so it does not block Phase 0.)_
- [x] **G0-6 Add a consistency script** `scripts/check_specs.py` (agent-only):
      verify status values, required sections, unique IDs, AC/FR links, INDEX
      counts. Wire into CI as a non-blocking check initially.
      _(clean on errors, 15 accurate warnings; CI job `spec-check` is
      `continue-on-error: true`.)_

**Ask owner (feature gate):**
- **G0-Q1** — `CLAUDE.md` and `INDEX.md:48` say F-004 is an intentionally empty
  scaffold the owner will author, but the file is populated, `Accepted`, and
  dated 2026-10-28. Was it authored by the owner? If yes, update both prose
  statements; if not, revert it to a scaffold. Do not touch F-004 before this
  is answered. _(still open — F-004 and its index prose untouched.)_
- **G0-Q2** — Is F-001's `Completed` intended to mean "Accepted and shipped",
  or just "authoring finished"? (Recommend: `Accepted`; it is the scope
  authority, not a shippable feature.)
  _(normalised to `Accepted` per G0-3; confirm or revert.)_

**Exit:** corpus committed, INDEX truthful, A-001 + 3 ADRs exist, spec check
passes, F-004 authorship answered.
_State: everything except the F-004 answer. Corpus is committed on
`docs/spec-baseline` and awaits review/merge; A-001 + ADR-001/002/003 exist;
`scripts/check_specs.py` exits 0 with warnings; INDEX is truthful except the
F-004 note._

## Phase 1 — contracts and foundations

### 1. F-001 Product scope and surfaces
- Auto: fix status, add missing sections as scaffolds, extract §8 process model
  into A-001, align surface tiers with F-013/F-016/F-019 wording.
- Ask owner: auth UX choice (passphrase/PIN/WebAuthn at `F-001:107`), session
  timeout default (15 min), and whether Tier 2 (KDE/iCal) remains in v1 scope.
- Exit: status `Accepted`, A-001 references it, no invalid status values.

### 2. F-002 Canonical item and source taxonomy (Accepted)
- Auto: implement the contract; move the Pydantic `Item`/attachment schema and
  hash-field list into A-001 §7/§6 as the canonical data contract, leaving a
  link in F-002. Build with unit tests for every FR-1…FR-10 and AC-1…AC-7.
- Ask owner: nothing (all Q-002-01…04 resolved).
- Exit: implementation green, F-002 `Implemented`; this is the type contract
  every later spec imports.

### 3. F-015 Local API contract and security
- Auto: extract envelope/error/versioning shapes into A-001 §6; propagate the
  selected security model from ADR-003; add an OpenAPI export check.
- Ask owner: the `proposal`-tagged rules that become user-visible contract —
  payload limits (2 MB / 35 MB), origin allowlist (including
  `vscode-webview://*`), and the 307 redirect grace for legacy routes. Confirm
  or amend; these harden into compatibility promises.
- Exit: F-015 `Accepted`, every implementation endpoint can be generated.

### 4. F-003 Change tracking and history
- Auto: move SQL DDL into A-001 §7; define the `analyses` table and its
  invalidation contract there; implement retention pruning mechanics.
- Ask owner: FR-8/FR-9 retention defaults (90 days / 2 snapshots) are
  `proposal`-sourced. Accept or amend. This is product-visible data deletion.
- Exit: F-003 `Accepted`, then implement and mark `Implementing`.

## Phase 2 — data plane

### 5. F-019 Brightspace crawler (In review → Accepted → implement)
- Auto: add compatibility/migration section; resolve Q-4 packaging via
  ADR-002; move deployment/filesystem layout (§5) and schema highlights (§8)
  into A-001; keep behaviour, coverage, mutation and auth rules in F-019.
- Ask owner: only if scope changes — L3 coverage list and Tier 1/2 mutation
  boundaries are already owner-resolved. Do **not** re-ask them.
- Exit: crawler service passes its own ACs; F-019 `Implemented`; REST/MCP
  contract frozen for F-004.

### 6. F-004 Brightspace sync integration (Accepted, blocked by G0-Q1)
- Auto: implement the thin integration layer against the frozen F-019 API;
  proxy triggers/mutations; add integration tests for crawler-down and slow
  responses.
- Ask owner: nothing if G0-Q1 resolution confirms the accepted text. If the
  file must be reverted to a scaffold, stop and let the owner author it.
- Exit: F-004 `Implemented`.

### 7. F-005 Email ingestion
- Auto: move blob layout/content-addressing into A-001 §7; implement adapters;
  implement attachment streaming (`/api/files/{sha256}`) per F-015.
- Ask owner: confirm the two resolved Qs that shape user entry points —
  attachment FTS deferred to background indexing, and Thunderbird = drop-dir +
  CLI import. If unchanged, proceed without a gate.
- Exit: F-005 `Accepted` → `Implemented`, migration alias
  (`outlook` → `email:<account>`) covered by a test.

## Phase 3 — intelligence

### 8. F-013 LLM provider, privacy, MCP
- Auto: move provider/router/secret/anonymizer component model into A-001 §5
  and A-001 §8; pick encryption library and key derivation (Q-013-01 already
  resolved to `cryptography`); implement adapters and both MCP transports.
- Ask owner: the `off` anonymization mode consent UX (FR-013-11), and confirm
  Q-013-02 (Tools first, Resources/Prompts in v1.1). Egress behaviour is
  feature-affecting.
- Exit: F-013 `Accepted` → `Implemented`; ADR-003 covers MCP auth.

### 9. F-006 Triage cascade and review workflow
- Auto: move cascade diagram, `analyses`/`labels` DDL and mode state machine
  into A-001; implement shadow/gate/trust modes; keep tuning constants
  agent-owned.
- Ask owner: confirm the trust-mode gate (100 verified items + accuracy ≥ 0.95,
  Q-006-03) — a safety promise — and the rule that labels are a presentation
  overlay (Q-006-02) if it changes what users see.
- Exit: F-006 `Accepted` → `Implemented`; calibration eval runs in CI.

### 10. F-007 Task briefs and study planning
- Auto: move ranking/budget/cache pipeline into A-001; reuse F-006's
  invalidation contract; implement MCP tools and calendar hooks.
- Ask owner: confirm the 60-day candidate horizon default and "no bundled OCR,
  fallback low-confidence/cloud vision" (Q-007-01). Both are product defaults.
- Exit: F-007 `Accepted` → `Implemented`; grounding constraints have tests.

## Phase 4 — operations and data lifecycle

### 11. F-016 CLI and service operations
- Auto: use ADR-003 for auth; fix the sync route drift from G0-5; extract
  systemd unit + dispatch flow to A-001; implement proxy and offline modes.
- Ask owner: only confirm Linux-only v1.0 (Q-016-01, already resolved) — no new
  gate expected.
- Exit: F-016 `Accepted` → `Implemented`.

### 12. F-018 Export, backup and migration
- Auto: add the missing acceptance-criteria and open-questions sections *as
  scaffolds*; move the migration engine into A-001 §7/§15 and ADR-001; label
  the §9 failure-mode table sources.
- Ask owner (this spec has the largest feature surface): backup retention
  (7/daily 03:00), pinned manual backups, exact portable-export contents, the
  new Settings "Data & Backups" tab, and restore-maintenance-mode UX
  (503 page wording). Nothing here can be invented.
- Exit: F-018 `Accepted` → `Implemented`; restore drill passes against a
  seeded database.

## Phase 5 — baseline UI/product specs (author, then implement)

These have no files. Author them one at a time as owner-led specs; the agent
scaffolds, asks the listed question, and does not fill behaviour.

| Order | ID | Owner question to open with |
|---|---|---|
| 13 | F-008 Web IA | Final nav model: keep seven areas or consolidate? |
| 14 | F-009 Inbox | Which keyboard shortcuts/label filters are required in v1? |
| 15 | F-010 Tasks/Today | Definition of "due", overdue and submitted handling |
| 16 | F-011 Search | FTS vs LIKE, prefix semantics, total counts |
| 17 | F-012 Calendar/notify | Feed window, UID stability, alarm/notification rules |
| 18 | F-014 System/errors | What is safe to expose, log retention, health checks |
| 19 | F-017 Desktop | Keep, rebuild on the contract, or drop (default: drop from v1) |

After each is authored and accepted, implement against A-001 and the F-015
contract.

## Design assessment

### What is good

- Feature specs are behaviour-first, numbered, testable, and explicitly
  owner-authored. FR/AC ID stability and `Source` tagging are solid.
- F-002/F-003/F-006/F-007/F-019 are unusually complete: failure modes, test
  plans and resolved decisions are present.
- The precedence order in `specs/README.md` is the right one.

### Problems

1. **No architecture layer.** `specs/architecture/` contains only its README,
   yet the acceptance gate requires checking features against an architecture
   spec. As a result every feature spec embeds architecture: SQL DDL
   (F-003/F-006/F-019), component diagrams (F-013), systemd units (F-001/F-016),
   filesystem/blob layouts (F-018/F-019), security model (F-015), config
   schemas (F-013/F-018), CLI dispatch (F-016). This duplicates contracts and
   has already produced drift (sync route, daemon token).
2. **Status vocabulary is not enforced.** F-001 says `Completed`; INDEX still
   calls F-004 a scaffold while the file is `Accepted`; counts are stale.
3. **`proposal` rules are load-bearing.** F-001, F-003 retention, F-015
   envelope/limits, F-018 rules are tagged proposal but treated as if settled.
   They must be owner-confirmed before acceptance.
4. **Missing required sections** block the stated acceptance gate: F-018 has no
   ACs or open questions; F-019 has no compatibility/migration; F-013/F-016/
   F-007 lack compatibility/migration; F-001 lacks edge cases.
5. **Shared concepts are defined nowhere.** The `analyses`/`labels` tables,
   input-hash invalidation formula, and provider budget contract are each
   alluded to in 3+ specs.
6. **Wrong layer for stable contracts.** F-002 (item model) and F-003 (change
   model) are really domain contracts; keeping their schema only in feature
   prose means implementation copies drift.

### Recommendation: three layers, one architecture baseline first

Adopt three layers, but do not pre-split the architecture into many files:

```text
specs/
  features/          behaviour only (FR/AC, flows, UX, edge cases)
  architecture/      A-001 system structure + contracts (start with one file)
  architecture/      ADR-NNN hard-to-reverse decisions
  plans/             execution plan + agent decision log (not authority)
```

- **Feature specs** keep: user problems, flows, FRs/ACs, edge cases, UX,
  privacy/security requirements *as behaviour*, migration notes. They **lose**
  DDL, component diagrams, file layouts, config schemas, systemd units, CLI
  dispatch internals — replaced by links to A-001/ADRs.
- **`A-001-runtime-contracts-persistence.md`** becomes the single architecture
  baseline covering the 16 required sections: runtime/process model, component
  boundaries, dependency rule, canonical data model, API envelope, config and
  secrets, lifecycle, observability, security, packaging, testing gates,
  migrations. Split into `A-002-persistence`, `A-003-api-security`,
  `A-004-intelligence` **only when a section outgrows a readable sitting**
  (rule of thumb: >250 lines or two independent owners).
- **ADRs** hold the irreversible calls (SQLite, crawler as a separate service,
  local auth model, encryption, dual MCP transport). Feature specs may then say
  "see ADR-003" instead of restating security rules.
- **F-002 and F-003 stay feature specs** for their behaviour, but their data
  contracts move to A-001 §7, which becomes the importable schema authority.
- **Add `scripts/check_specs.py`** so structure (not prose) is enforced: valid
  statuses, required headings, FR/AC IDs, INDEX counts, links. This is the
  only reliable defence against the current drift.

This gives the owner a small, reviewable set of feature decisions while the
agent owns a single architecture document and a decision log — matching the
"ask only about features" rule without losing architectural rigour.

## Progress tracking

Update this file when a phase or spec completes:

- change the spec status in its metadata **and** INDEX;
- append the owner's answers to the spec change log with `Source: owner`;
- log architecture calls in [decisions.md](decisions.md);
- write/refresh `HANDOFF.md` at each phase boundary so a fresh session can
  resume without re-deriving context.

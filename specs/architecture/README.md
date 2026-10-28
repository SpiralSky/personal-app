# Architecture specifications

This directory holds the architecture baseline and its decision records. The
feature specs define behaviour; this layer defines structure and contracts.

## Inventory

| ID | Document | Status |
|---|---|---|
| A-001 | [Runtime contracts and persistence](A-001-runtime-contracts-persistence.md) | Accepted |
| ADR-001 | [SQLite and forward-only migrations](ADR-001-sqlite-and-migrations.md) | accepted |
| ADR-002 | [Crawler as a separate service](ADR-002-crawler-as-separate-service.md) | accepted |
| ADR-003 | [Local API security model](ADR-003-local-api-security-model.md) | accepted |

A-001 covers all sixteen required sections below in one readable file. Split it
only when a section outgrows a sitting (>250 lines or two independent owners),
as `A-002-persistence`, `A-003-api-security`, `A-004-intelligence`.

## Purpose

The architecture spec defines **how the system is structured**, not what the product does. It should be:

- derived from the feature specs and the [codebase assessment](../../docs/codebase-assessment.md);
- specific enough to constrain implementation;
- verified against code, tests and CI rather than trusted as prose;
- small enough to read in one sitting.

## Required sections

When written, an architecture spec should cover:

1. **Context and constraints** — local single-user app, supported OS, offline behaviour, optional external LLMs.
2. **Quality attributes** — privacy, reliability, performance, maintainability, testability.
3. **System boundaries** — what is in scope, what is explicitly out.
4. **Component model** — domain, application, ports, adapters, transport, UI.
5. **Dependency rule** — which layer may import which.
6. **Contracts** — API request/response models, generated OpenAPI, generated TS client, event shapes.
7. **Data model and persistence** — entities, invariants, schema versioning, migrations.
8. **Configuration and secrets** — single loader, precedence, validation, what is runtime-mutable.
9. **Lifecycle and concurrency** — startup/shutdown, task ownership, background work, coalescing.
10. **Error handling and observability** — error taxonomy, logging, persisted events, health checks.
11. **Security and privacy** — local auth, CSRF/Origin, data egress, secret handling.
12. **Frontend architecture** — routing, data fetching, component boundaries, accessibility.
13. **Packaging and deployment** — dev checkout vs installed package, supported surfaces, update path.
14. **Testing strategy and CI gates** — unit, integration, contract, e2e; required checks.
15. **Migration and rollback** — database, data export, cutover.
16. **Decision log** — links to ADRs.

## Decision records

Use `ADR-NNN-<slug>.md` for decisions that are hard to reverse or likely to be questioned later. Each ADR should contain:

- context;
- decision;
- alternatives considered;
- consequences;
- status (`proposed`, `accepted`, `superseded`);
- links to affected feature specs.

## Verification rule

A model-vetted architecture claim is not evidence. Every non-obvious claim should point to:

- a test or contract check;
- a CI result;
- a code reference;
- or an explicit decision that cannot yet be verified.

A-001 tags unverified decisions **[target]**. This repository already contains
examples of documentation claiming fixes that were never implemented (see
Appendix B of the assessment). Treat prose as untrusted until verified.

Structural health of the corpus (status values, required sections, IDs, INDEX
counts, links) is checked by `scripts/check_specs.py` (roadmap G0-6).

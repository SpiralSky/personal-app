# Architecture specifications

This directory is reserved for the architecture specification and its decision records. It is intentionally empty of decisions until the architecture has been written and vetted.

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

This repository already contains examples of documentation claiming fixes that were never implemented (see Appendix B of the assessment). Treat prose as untrusted until verified.

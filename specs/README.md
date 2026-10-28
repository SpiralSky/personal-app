# Specifications

This directory is the authoritative description of **what the product should become**. It is deliberately separate from the current implementation.

## Precedence

When documents disagree, use this order:

1. **Accepted feature spec** — desired behaviour, user-facing rules and acceptance criteria.
2. **Accepted architecture spec** — system boundaries, contracts and quality attributes.
3. **`docs/codebase-assessment.md`** — factual snapshot of the current implementation.
4. **Current code, README, CHANGELOG and issue trackers** — evidence only, never authority.

Feature specs **may overhaul or override** current behaviour. If a spec intentionally breaks compatibility, it must say so explicitly in its “Compatibility and migration” section.

## Layout

```text
specs/
  README.md                 this file: authority, workflow, conventions
  features/
    README.md               how to write feature specs
    INDEX.md                registry of feature specs and candidate areas
    TEMPLATE.md             copy this to start a new feature spec
    F-NNN-<slug>.md         one file per feature
  architecture/
    README.md               architecture-spec placeholder and required sections
    A-NNN-<slug>.md         one file per architecture area (when written)
    ADR-NNN-<slug>.md       architecture decision records
```

## Workflow

```text
Baseline -> Draft -> In review -> Accepted -> Implementing -> Implemented
                         |                         |
                         +---- Superseded <--------+
```

| Status | Meaning |
|---|---|
| **Baseline** | Current behaviour, documented but not yet re-decided |
| **Draft** | Being written; not authoritative yet |
| **In review** | Ready for critique, model vetting or user sign-off |
| **Accepted** | Authoritative; implementation may start |
| **Implementing** | Accepted and actively being built |
| **Implemented** | Built and verified against acceptance criteria |
| **Superseded** | Replaced by another spec; keep for history, add a link |

A spec is not “Accepted” until:

- every functional rule has an ID (`FR-N`);
- every acceptance criterion is testable (`AC-N`);
- edge cases and failure modes are listed;
- compatibility/migration is addressed;
- open questions are either answered or explicitly deferred;
- the feature spec has been checked against the architecture spec.

## Naming

Use a stable identifier prefix plus the feature or decision name as a short slug:

- Feature: `F-001-item-and-change-model.md`
- Architecture: `A-001-runtime-and-boundaries.md`
- Decision: `ADR-001-sqlite-and-migrations.md`

The prefix and zero-padded number are the document's **stable identifier**: they make cross-references ("see F-004"), ordering and supersession possible without depending on a title that may evolve. The slug is the **name** in lowercase kebab-case, and the document's heading is that name — do not put the number in the heading.

Keep slugs short and descriptive: a feature name, not a module path or a list of components. A filename is a permanent link target, so renaming it later breaks references; renaming is acceptable while a spec is Draft, never after acceptance. Never renumber an accepted spec; mark it superseded instead.

## Feature spec vs architecture spec

| Feature spec | Architecture spec |
|---|---|
| User-visible behaviour | System structure |
| Rules, flows, edge cases | Boundaries, contracts, data flow |
| Acceptance criteria | Quality attributes and constraints |
| May override current behaviour | Constrains how features are implemented |
| Owned by product/behaviour | Owned by engineering |

Feature specs should reference architecture decisions, not restate them. Architecture specs should reference feature IDs, not redefine behaviour.

## Working with a new session

Start here:

1. Read [docs/codebase-assessment.md](../docs/codebase-assessment.md) for the factual baseline.
2. Read [features/INDEX.md](features/INDEX.md) and pick one feature.
3. Read [architecture/README.md](architecture/README.md) before making structural decisions.
4. Copy [features/TEMPLATE.md](features/TEMPLATE.md) to `features/F-NNN-<slug>.md`.
5. Keep the index updated when status changes.

Do not infer requirements from the current code alone. The assessment lists behaviours worth preserving, but the feature spec decides what the product should do.

## Guiding rules

- **Behaviour first, implementation second.** A feature spec must be understandable without reading source code.
- **One feature per spec.** If it needs two “and”s in the title, split it.
- **Testable language.** Prefer “the API returns 404 when …” over “handle errors gracefully”.
- **Explicit overrides.** If current behaviour is being replaced, say what changes and why.
- **Owner decides.** Agents may scaffold, propose and edit, but only the owner accepts a rule. Mark proposals explicitly so they cannot be mistaken for requirements.
- **No hidden state.** Document caches, background jobs, retries and persistence that affect user-visible behaviour.
- **Privacy is a requirement.** State which data leaves the machine and under what conditions.
- **Link, don’t duplicate.** Reference the assessment or an architecture decision instead of copying it.

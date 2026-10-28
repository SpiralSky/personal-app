# Feature name

| Field | Value |
|---|---|
| ID | F-NNN |
| Status | Draft |
| Owner | |
| Created | YYYY-MM-DD |
| Last updated | YYYY-MM-DD |
| Target release | |
| Related architecture | `A-NNN`, `ADR-NNN` |
| Supersedes | — |
| Superseded by | — |

## 1. Summary

One paragraph: what this feature is and why it matters. A reader should understand the change without reading the rest of the document.

## 2. Problem and context

- What user problem does this solve?
- What happens today? Link to the current behaviour in [the assessment](../../docs/codebase-assessment.md) where useful.
- Why is a change needed now?

## 3. Users and jobs

| User | Job / need | Notes |
|---|---|---|
| | | |

## 4. Goals and non-goals

**Goals**

- G-1:
- G-2:

**Non-goals**

- NG-1:
- NG-2:

## 5. Current behaviour (baseline)

Brief description of the current implementation and its known gaps. This section is evidence, not a requirement. If the feature overrides current behaviour, say so here.

## 6. Desired behaviour

Describe the feature as if it already worked. Cover:

- primary flow;
- alternate flows;
- empty, loading, partial and offline states;
- error and recovery behaviour;
- what the user sees and can do.

## 7. Functional rules

Number every rule so tests and reviews can refer to it.

| ID | Rule |
|---|---|
| FR-1 | |
| FR-2 | |

Include defaults, precedence and validation rules. If a rule depends on a mode or flag, state every mode.

## 8. Data and contracts

### 8.1 Entities and fields

| Entity | Field | Type | Required | Rules |
|---|---|---|---|---|
| | | | | |

### 8.2 API / CLI surface

| Method | Path / command | Request | Response | Errors |
|---|---|---|---|---|
| | | | | |

### 8.3 Persistence and retention

- What is stored?
- For how long?
- What is user-visible vs internal?
- What is hashed, cached or derived?

## 9. Edge cases and failure modes

| Case | Expected behaviour |
|---|---|
| Dependency unavailable | |
| Duplicate input | |
| Invalid date/time | |
| Partial fetch | |
| Concurrent action | |
| Permission/credential failure | |

## 10. UX and accessibility

- Layout and interaction notes.
- Keyboard shortcuts.
- Screen-reader labels, focus behaviour and contrast.
- Mobile/narrow-window behaviour.

## 11. Non-functional requirements

| Area | Requirement |
|---|---|
| Performance | |
| Privacy | Which data leaves the machine, to which provider, under what consent? |
| Security | |
| Reliability | |
| Observability | |

## 12. Compatibility and migration

- **Breaking:** yes / no
- **What changes:**
- **Existing data:**
- **Migration:**
- **Rollback:**
- **Deprecation window:**

## 13. Acceptance criteria

Use Given/When/Then. Each criterion must be automatable or explicitly marked as manual.

| ID | Given | When | Then | Test level |
|---|---|---|---|---|
| AC-1 | | | | unit / integration / e2e / manual |

## 14. Test plan

- Unit:
- Integration:
- End-to-end:
- Manual/exploratory:
- Regression risks:

## 15. Open questions and decisions

| ID | Question | Owner | Resolution | Date |
|---|---|---|---|---|
| Q-1 | | | | |

Use `OPEN:` in the body for unresolved questions; resolve or defer them before moving to **Accepted**.

## 16. Out of scope / future work

- 

## 17. Change log

| Date | Change | By |
|---|---|---|
| | Initial draft | |

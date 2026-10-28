# Agent architecture decisions

Append-only log of decisions the agent made without asking the owner. One entry
per non-trivial choice. If a decision turns out to constrain feature behaviour,
stop and raise it as a feature question instead.

Format:

```md
## AD-YYYYMMDD-NN — <decision>

- **Status:** proposed | accepted | superseded
- **Context:** what forced the choice
- **Decision:** what was chosen
- **Alternatives:** what was rejected and why
- **Consequences:** what becomes hard later
- **Affects:** F-NNN, A-NNN
```

Promote decisions that are hard to reverse into `specs/architecture/ADR-NNN-*.md`
and link them here.

---

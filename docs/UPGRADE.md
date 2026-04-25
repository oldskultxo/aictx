# Upgrade guide

## Current line: 4.2.x

Current documented runtime: `4.2.1`.

For users already on recent `4.x`, there is no special manual migration workflow beyond re-running the normal setup paths when needed:

```bash
aictx install
aictx init --repo .
```

The important `4.x` changes are behavioral, not a new user-facing migration command.

## 4.2.x

### Added

- public `aictx next`
- structured continuity brief JSON for `next --json`
- richer compact/final execution summaries
- prepared/final/effective task and area classification for better continuity traceability

### Notes

- agents should treat `agent_summary_text` as the canonical factual summary source
- `finalize` can now correct provisional task/area classification with observed execution evidence

## 4.0.0

### Breaking changes

- AICTX moved to the repo-local continuity runtime contract
- continuity artifacts were standardized under `.aictx/continuity/`
- visible-session startup banner behavior became part of the runtime contract
- packet/context middleware became conservative and task-dependent rather than universal

### Migration notes

- re-run `aictx init` in initialized repositories
- remove assumptions about legacy pre-4.0 layouts or broad hidden continuity behavior

## 3.0.0

### Breaking changes

- `.aictx/memory/source/` became the canonical editable source-knowledge layer
- legacy source locations stopped being canonical
- generated/runtime folders under `.aictx/boot`, `.aictx/store`, `.aictx/indexes`, `.aictx/metrics`, and similar should not be hand-edited
- AICTX no longer ships knowledge mods / `.aictx/library`
- AICTX no longer ships global metrics aggregation

## 2.0.0

### Breaking changes

- `aictx install` no longer modifies global Codex configuration by default
- use `aictx install --install-codex-global` for global Codex files
- `aictx init` consolidates repo-local Codex guidance into `AGENTS.md`
- re-running `aictx init` preserves logs, feedback, and strategy memory

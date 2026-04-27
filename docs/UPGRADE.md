# Upgrade guide

## Current line: 4.5.x

Current documented runtime: `4.5.2`.

For users already on recent `4.x`, there is no special manual migration workflow beyond re-running the normal setup paths when needed:

```bash
aictx install
aictx init --repo .
```

The important `4.x` changes are behavioral, not a new user-facing migration command.

## 4.5.x

### Added

- repo-local Work State under `.aictx/tasks/` with public `aictx task start|status|list|show|update|resume|close`
- active Work State loading in prepare/startup/`aictx next`, plus conservative finalize updates
- `report real-usage` Work State visibility for active task id/status/thread count/last update time and recent status counts
- `--from-file` task patch input, compact `changed_fields` update output, and internal `--work-state-file` runtime payloads
- `docs/WORK_STATE.md` for artifact, CLI, and runtime behavior
- minimal branch-safe Work State loading using saved git branch/head context.
- Work State created on a merged feature branch can still load on main when the saved commit is reachable from current HEAD.
- Dirty Work State from another branch is skipped to avoid unsafe continuation.

### Notes

- no manual migration is required; rerun `aictx init --repo .` if you want regenerated runner guidance and eager `.aictx/tasks/` scaffold
- Work State is operational continuity only; it is not a planner, kanban, or issue tracker

## 4.4.x

### Added

- toolchain-aware `error_events` for observed command/test/lint/type/build/compile failures
- structured failure pattern persistence with toolchain, phase, code, path, line, command, exit code, and fingerprint when available
- backward-compatible derivation of `notable_errors` from structured events
- failure lookup that can rank by toolchain, phase, code, fingerprint, text, area, and paths
- final summaries that distinguish new learned failures, repeated known patterns, resolved prior failures, and related failure context that was only considered
- `report real-usage` error-capture metrics for event counts, toolchains, phases, and failure patterns with structured events

### Notes

- no manual migration is required; rerun `aictx init --repo .` if you want regenerated runner guidance and runtime files
- failure capture is strongest for commands run through `aictx internal run-execution` or integrations that pass explicit execution/error signals
- AICTX does not claim an error was avoided unless the observed execution state supports that wording

## 4.3.x

### Added

- public `aictx map status|refresh|query`
- optional RepoMap runtime outputs under `.aictx/repo_map/`
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

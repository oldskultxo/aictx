# Technical overview

## Product shape

`aictx` is a repo-local continuity runtime for coding agents.

Current public CLI:

- `aictx install`
- `aictx init`
- `aictx suggest`
- `aictx reflect`
- `aictx reuse`
- `aictx next`
- `aictx task start|status|list|show|update|resume|close`
- `aictx map status|refresh|query`
- `aictx report real-usage`
- `aictx clean`
- `aictx uninstall`

Internal runtime commands remain available under `aictx internal ...` for middleware, hooks, wrappers, and runner integrations.

## Core runtime flow

The runtime is built around one simple loop:

1. prepare execution
2. run task
3. finalize execution
4. expose startup/final summary texts when required
5. persist reusable data
6. reuse it on later executions

## Prepare

`prepare_execution()` currently:

- builds an execution envelope
- resolves a provisional task type
- derives a provisional area id from currently known paths
- loads repo bootstrap sources and effective preferences
- may build packet-oriented context for non-trivial work
- loads repo-local continuity layers:
  - session identity
  - handoff and recent handoff history
  - decisions
  - failure patterns, including structured toolchain error events when available
  - semantic repo memory
  - procedural reuse
  - staleness markers
- may include RepoMap status when available
- loads active Work State from `.aictx/tasks/active.json` / `.aictx/tasks/threads/<task-id>.json` when present
- may inject `execution_hint` when a reusable strategy matches
- may return `startup_banner_text` with show-once-per-visible-session semantics

## Finalize

`finalize_execution()` currently:

- appends execution telemetry and real execution logs
- recalculates task classification from observed evidence
- recalculates area id from observed files/tests when possible
- exposes:
  - `prepared_task_type` / `prepared_area_id`
  - `final_task_type` / `final_area_id`
  - `effective_task_type` / `effective_area_id`
  - `final_task_resolution`
- persists validated learning where enabled
- persists strategy memory
- records, recognizes, or resolves failure memory
- persists handoff / decisions / semantic continuity artifacts
- may conservatively update active Work State from factual execution evidence or explicit runtime payloads
- updates continuity metrics
- returns `agent_summary` and `agent_summary_text`

## Real data sources

Main repo-local artifacts:

```text
.aictx/continuity/session.json
.aictx/continuity/handoff.json
.aictx/continuity/handoffs.jsonl
.aictx/continuity/decisions.jsonl
.aictx/continuity/semantic_repo.json
.aictx/continuity/dedupe_report.json
.aictx/continuity/staleness.json
.aictx/continuity/continuity_metrics.json
.aictx/continuity/last_execution_summary.md
.aictx/tasks/active.json
.aictx/tasks/threads/<task-id>.json
.aictx/tasks/threads/<task-id>.events.jsonl
.aictx/metrics/execution_logs.jsonl
.aictx/metrics/execution_feedback.jsonl
.aictx/strategy_memory/strategies.jsonl
.aictx/failure_memory/failure_patterns.jsonl
.aictx/area_memory/areas.json
```

## Classification model

Task/area typing is deterministic and evidence-based.

Current shape:

- `prepare` gives a provisional classification from explicit metadata, prompt, and currently known files
- `finalize` can reclassify from observed files, tests, commands, errors, and result summary
- AICTX preserves both the initial guess and the final/effective values for traceability

This improves continuity quality but remains heuristic, not semantic understanding.

## Failure capture and memory

AICTX 4.4 normalizes observed failures into `error_events` where possible. Events are compact dictionaries with `toolchain`, `phase`, `severity`, `message`, `code`, `file`, `line`, `command`, `exit_code`, and `fingerprint`.

The runtime can parse common output from Python/pytest/mypy/ruff/pyright, JS/TS/npm/tsc/ESLint/Jest/Vitest, Go, Rust/Cargo, Java/JVM/Maven, .NET, C/C++, Ruby, PHP, and unknown failed commands through a generic fallback.

Failure records remain repo-local in `.aictx/failure_memory/failure_patterns.jsonl`. They are used as debugging/avoidance context, not as positive strategy reuse. Summaries distinguish new learned patterns, repeated known patterns, resolved prior failures, and related context that was only considered.

## Strategy reuse

Strategy reuse is conservative and explainable.

Current matching can consider:

- task type
- prompt similarity
- overlapping files
- primary entry point
- commands/tests/errors
- structured error event fingerprints/codes when available through failure memory
- area
- recency
- real execution evidence

Failed strategies remain stored for history/debugging but are excluded from positive reuse.

## Agent-facing operational commands

### `aictx suggest`
Returns deterministic next-step guidance from reusable strategy memory.

### `aictx reflect`
Returns a small deterministic diagnosis over recent exploration patterns.

### `aictx reuse`
Returns the latest reusable successful strategy.

### `aictx next`
Returns compact continuity guidance for the next session or next step.
It can also emit structured JSON with the continuity brief and `why_loaded` evidence.
When active Work State exists, it has priority over older historical continuity layers.

### `aictx task ...`
Returns or mutates the deterministic repo-local Work State artifact for the active task.
This is operational continuity, not planning or issue tracking.
Stored threads can be listed, shown, resumed, or closed with a final explicit patch.

### `aictx map ...`
Optional RepoMap structural operations for status, refresh, and query.

### `aictx report real-usage`
Returns aggregated real runtime usage from stored logs/feedback/continuity metrics.
It also exposes a compact Work State snapshot (`active`, `task_id`, `status`, `threads_count`, `last_updated_at`).
The snapshot includes `recent_statuses` counts across stored task threads.

## Runner integration

### Codex
Repo guidance is written into:

- `AGENTS.md`
- `.aictx/agent_runtime.md`

Optional global Codex files can be installed with `--install-codex-global`.

### Claude
Repo guidance is written into:

- `CLAUDE.md`
- `.claude/settings.json`
- `.claude/hooks/*`

The integrations guide prepare/finalize usage and final-response summary behavior.
Enforcement still depends on runner support and agent cooperation.

## Design principles

- real data over invented metrics
- deterministic logic over opaque ranking
- repo-local artifacts over hidden cross-repo state
- continuity from observed executions over magical memory claims

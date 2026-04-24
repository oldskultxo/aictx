# Technical overview

## Product shape

`aictx` is a repo-local continuity runtime for coding agents.

The public surface is intentionally small:

- `aictx install`
- `aictx init`
- `aictx suggest`
- `aictx reflect`
- `aictx reuse`
- `aictx report real-usage`
- `aictx clean`
- `aictx uninstall`

Under that surface, the runtime still contains internal commands and compatibility layers used by middleware and runner integrations.
Legacy knowledge mods and global aggregation are intentionally not part of the v4 continuity contract.

## Core runtime flow

The runtime is built around one simple loop:

1. prepare execution
2. run task
3. finalize execution
4. expose `agent_summary_text` for the final user response
5. persist reusable data
6. reuse it on later executions

### Prepare

`prepare_execution()` currently does these things:

- builds an execution envelope
- resolves task type
- loads repo bootstrap sources
- may build packet-oriented context for non-trivial work
- loads continuity layers from repo-local artifacts
  - session identity
  - handoff
  - recent decisions
  - failure patterns
  - semantic repo memory
  - procedural reuse
  - staleness markers
- if a previous successful strategy exists, injects an `execution_hint`

### Execute

The agent then executes normally.

`aictx` does not replace the agent loop. It adds runtime data around it.

### Finalize

`finalize_execution()` currently does these things:

- appends a real execution log
- appends operational feedback
- persists validated learning where enabled
- persists strategy memory for successful validated runs
- records failure events on unsuccessful runs
- persists handoff / decisions / semantic continuity artifacts
- updates aggregate continuity metrics
- returns `agent_summary` and `agent_summary_text`

## Real data sources

The main real-data files are:

```text
.aictx/continuity/session.json
.aictx/continuity/handoff.json
.aictx/continuity/decisions.jsonl
.aictx/continuity/semantic_repo.json
.aictx/continuity/dedupe_report.json
.aictx/continuity/staleness.json
.aictx/continuity/continuity_metrics.json
.aictx/metrics/execution_logs.jsonl
.aictx/metrics/execution_feedback.jsonl
.aictx/strategy_memory/strategies.jsonl
.aictx/failure_memory/failure_patterns.jsonl
```

### Execution logs

Each execution log is based only on observed runtime data, for example:

- task id
- timestamp
- task type
- files opened
- files reopened
- execution time
- success
- packet usage

If a field is not available yet, it remains empty or null rather than being inferred.

### Execution feedback

Feedback is operational, not narrative.

It summarizes real facts such as:

- files opened count
- reopened files count
- packet usage
- strategy reuse
- simple redundant exploration detection

### Strategy memory

Strategy memory is append-only. Successful executions can become reusable strategy hints; failed executions are retained for history/debugging but excluded from positive reuse.

Current schema stores observed execution signals such as task id/type, entry points, files used, command/test/error hints, area, success, and timestamp.

There is no ML layer or synthetic scoring. Reuse ranking is deterministic and explainable.

### Continuity artifacts

Continuity artifacts are repo-local and layered:

- `session.json` -> stable repo/agent session identity
- `handoff.json` -> latest canonical continuation handoff
- `decisions.jsonl` -> append-only significant decisions
- `semantic_repo.json` -> compact subsystem-level repo knowledge
- `dedupe_report.json` -> non-destructive hygiene output
- `staleness.json` -> markers used to down-rank or exclude stale memory
- `continuity_metrics.json` -> aggregate counts of real continuity reuse/load events

These artifacts help a new session continue prior work without claiming hidden semantic intelligence.

## Strategy reuse

Strategy reuse is deliberately conservative.

Current behavior:

- exclude failed strategies from reuse
- prefer matching task type and related execution signals when available
- consider prompt similarity, overlapping files, primary entry point, commands/tests/errors, area, and recency
- expose the selected strategy as `execution_hint`

The runtime does not claim ML-grade semantic retrieval or guaranteed optimization.

## Agent-facing commands

### `aictx suggest`

- source: strategy memory
- returns: suggested entry points and files from the latest matching strategy

### `aictx reflect`

- source: latest execution log
- returns: simple exploration warning from real reopened/opened file data

### `aictx reuse`

- source: strategy memory
- returns: latest reusable successful execution pattern

### `aictx report real-usage`

- source: execution logs + execution feedback
- optional source: continuity metrics
- returns: real aggregated runtime usage only

## Runner integration

### Codex

Repo guidance is written into:

- `AGENTS.md`
- `.aictx/agent_runtime.md`

### Claude

Repo guidance is written into:

- `CLAUDE.md`
- `.claude/settings.json`
- `.claude/hooks/*`

The integrations make `aictx` discoverable, guide runtime usage, and require final responses for non-trivial tasks to include `agent_summary_text` after finalize. Enforcement still depends on runner support and agent cooperation.

This dependency is part of the contract:
- AICTX can only preserve continuity when the runner exposes repo instructions and the agent cooperates with prepare/finalize
- if the runner ignores repo instructions or suppresses runtime steps, continuity quality degrades

## Design principles

Current design choices are intentional:

- real data over synthetic metrics
- deterministic logic over opaque ranking
- small public surface over large command sprawl
- reuse of successful runs over speculative intelligence claims

## What remains intentionally simple

- file tracking is still incomplete
- strategy reuse is deterministic and heuristic, not ML-based
- continuity quality depends on runner/agent cooperation and available observed signals
- stale memory handling is conservative and may exclude clearly obsolete records while keeping history on disk
- no baseline comparison is reported unless real baseline data exists
- no claim of guaranteed speed or quality improvement is made

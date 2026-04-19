# Technical overview

## Product shape

`aictx` is a repo-local runtime layer for coding agents.

The public surface is intentionally small:

- `aictx install`
- `aictx init`
- `aictx suggest`
- `aictx reflect`
- `aictx reuse`
- `aictx report real-usage`

Under that surface, the runtime still contains internal commands and compatibility layers used by middleware and runner integrations.

## Core runtime flow

The runtime is built around one simple loop:

1. prepare execution
2. run task
3. finalize execution
4. persist reusable data
5. reuse it on later executions

### Prepare

`prepare_execution()` currently does these things:

- builds an execution envelope
- resolves task type
- loads repo bootstrap sources
- may build packet-oriented context for non-trivial work
- loads strategy memory by task type
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

## Real data sources

The main real-data files are:

```text
.ai_context_engine/metrics/execution_logs.jsonl
.ai_context_engine/metrics/execution_feedback.jsonl
.ai_context_engine/strategy_memory/strategies.jsonl
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

Strategy memory is append-only and based on real successful executions.

Current schema is intentionally minimal:

- `task_id`
- `task_type`
- `entry_points`
- `files_used`
- `success`
- `timestamp`

There is no scoring, ranking, clustering, or ML layer.

## Strategy reuse

Strategy reuse is deliberately conservative.

Current behavior:

- load strategies by exact task type
- take the most recent successful one
- expose it as `execution_hint`

The runtime does not claim deeper similarity matching than that.

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
- returns: real aggregated runtime usage only

## Runner integration

### Codex

Repo guidance is written into:

- `AGENTS.md`
- `AGENTS.override.md`
- `.ai_context_engine/agent_runtime.md`

### Claude

Repo guidance is written into:

- `CLAUDE.md`
- `.claude/settings.json`
- `.claude/hooks/*`

The purpose is not to force behavior, but to make `aictx` discoverable and easy to use during execution.

## Design principles

Current design choices are intentional:

- real data over synthetic metrics
- deterministic logic over opaque ranking
- small public surface over large command sprawl
- reuse of successful runs over speculative intelligence claims

## What remains intentionally simple

- file tracking is still incomplete
- strategy reuse is by task type only
- no baseline comparison is reported unless real baseline data exists
- no claim of guaranteed speed or quality improvement is made

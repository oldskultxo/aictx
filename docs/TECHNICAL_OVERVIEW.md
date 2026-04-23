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
- `aictx clean`
- `aictx uninstall`

Under that surface, the runtime still contains internal commands and compatibility layers used by middleware and runner integrations.

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
- returns `agent_summary` and `agent_summary_text`

## Real data sources

The main real-data files are:

```text
.aictx/metrics/execution_logs.jsonl
.aictx/metrics/execution_feedback.jsonl
.aictx/strategy_memory/strategies.jsonl
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
- returns: real aggregated runtime usage only

## Runner integration

### Codex

Repo guidance is written into:

- `AGENTS.md`
- `AGENTS.override.md`
- `.aictx/agent_runtime.md`

### Claude

Repo guidance is written into:

- `CLAUDE.md`
- `.claude/settings.json`
- `.claude/hooks/*`

The integrations make `aictx` discoverable, guide runtime usage, and require final responses for non-trivial tasks to include `agent_summary_text` after finalize. Enforcement still depends on runner support and agent cooperation.

## Design principles

Current design choices are intentional:

- real data over synthetic metrics
- deterministic logic over opaque ranking
- small public surface over large command sprawl
- reuse of successful runs over speculative intelligence claims

## What remains intentionally simple

- file tracking is still incomplete
- strategy reuse is deterministic and heuristic, not ML-based
- no baseline comparison is reported unless real baseline data exists
- no claim of guaranteed speed or quality improvement is made

# aictx

`aictx` is a repo-local runtime layer for coding agents.

It turns a repository into a place where an agent can:

- log real execution
- persist structured runtime data
- store successful strategies
- reuse those strategies on later tasks
- get lightweight guidance during execution

It does **not** claim synthetic performance gains, magic memory, or benchmark results that were not measured from real runs.

## What it is

`aictx` is for repositories where coding agents are used repeatedly.

It adds a small runtime contract around agent work:

- `prepare_execution()` can assemble context and reuse a previous successful strategy
- the agent runs normally
- `finalize_execution()` records real logs and feedback
- successful runs can be saved as strategy memory
- later runs can reuse that memory through runtime hints and CLI commands

## What it does today

Real, implemented capabilities:

- real execution logging in `.ai_context_engine/metrics/execution_logs.jsonl`
- real execution feedback in `.ai_context_engine/metrics/execution_feedback.jsonl`
- strategy memory in `.ai_context_engine/strategy_memory/strategies.jsonl`
- strategy reuse during `prepare_execution()`
- agent-facing CLI commands:
  - `aictx suggest`
  - `aictx reflect`
  - `aictx reuse`
  - `aictx report real-usage`
- repo-native integration hints for Codex and Claude

## What it is not

`aictx` is not:

- a prompt pack
- a benchmark engine
- a synthetic telemetry layer
- a replacement for Codex, Claude, or other coding agents

## Quick start

```bash
pip install aictx
aictx install
cd your-repo
aictx init
```

After that, use your coding agent normally inside the repo.

## Public CLI surface

The intended public surface is small:

```bash
aictx install
aictx init
aictx suggest
aictx reflect
aictx reuse
aictx report real-usage
```

Example:

```bash
aictx suggest --repo .
aictx report real-usage --repo .
```

## How it works

1. `prepare_execution()` runs before an execution.
   - resolves task type
   - may build packet-oriented context
   - may attach `execution_hint` from a previous successful strategy of the same task type
2. the agent executes the task
3. `finalize_execution()` runs after execution.
   - records real execution logs
   - records operational feedback
   - persists validated strategy memory for successful runs when applicable
4. later executions can reuse that strategy memory

## Real runtime artifacts

Main repo-local artifacts:

```text
.ai_context_engine/
  metrics/
    execution_logs.jsonl
    execution_feedback.jsonl
  strategy_memory/
    strategies.jsonl
```

Additional runtime files may exist for compatibility and existing integrations, but the files above are the main v1 data sources for real usage and strategy reuse.

## CLI commands

### `aictx suggest`

Reads strategy memory and returns deterministic next-step guidance.

Example output:

```json
{"suggested_entry_points": [], "suggested_files": [], "source": "none"}
```

### `aictx reflect`

Reads the latest real execution log and reports simple exploration issues.

Example output:

```json
{"reopened_files": [], "possible_issue": "none"}
```

### `aictx reuse`

Returns the latest reusable successful strategy.

Example output:

```json
{"task_type": "", "entry_points": [], "files_used": [], "source": "none"}
```

### `aictx report real-usage`

Aggregates only real execution logs and feedback.

Example output:

```json
{"total_executions": 0, "avg_execution_time_ms": null, "avg_files_opened": null, "avg_reopened_files": null, "strategy_usage": 0, "packet_usage": 0, "redundant_exploration_cases": 0}
```

## Runner integration

`aictx` writes repo-level instructions so agents can discover and use the runtime automatically.

Current guidance tells the agent to:

- run `aictx suggest --repo .` before opening too many files
- run `aictx reflect --repo .` when reopening the same file
- run `aictx reuse --repo .` for similar prior work
- run `aictx suggest --repo .` when unsure about the next step

## Honest limits

- strategy reuse is intentionally simple: latest successful strategy by task type
- file tracking is still minimal, so `files_opened` and `files_reopened` may remain empty
- there is no built-in ranking between strategies
- there is no guaranteed performance improvement
- real behavior still depends on the agent following repo instructions and hooks

See [docs/LIMITATIONS.md](docs/LIMITATIONS.md).

## Development

```bash
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -e . pytest build
make test
```

## Historical note

Synthetic benchmark code was removed from the product path.

Historical non-product benchmark material lives only under:

- `experiments/simulated/benchmark.py`
- `experiments/simulated/BENCHMARK_QUICKSTART.md`

## Read next

- [Technical overview](docs/TECHNICAL_OVERVIEW.md)
- [Demo](docs/DEMO.md)
- [Limitations](docs/LIMITATIONS.md)
- [Usage guide](docs/USAGE.md)

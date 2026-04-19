# Usage

## Install and initialize

```bash
pip install aictx
aictx install
aictx init
```

Use `--repo <path>` when initializing a repository outside the current directory.

## Public commands

### `aictx suggest`

Return deterministic next-step guidance from the latest stored strategy.

Data source:

- `.ai_context_engine/strategy_memory/strategies.jsonl`

Example:

```bash
aictx suggest --repo .
```

Example output:

```json
{"suggested_entry_points": [], "suggested_files": [], "source": "none"}
```

### `aictx reflect`

Inspect the latest real execution log and report a simple exploration issue.

Data source:

- `.ai_context_engine/metrics/execution_logs.jsonl`

Example:

```bash
aictx reflect --repo .
```

Example output:

```json
{"reopened_files": [], "possible_issue": "none"}
```

### `aictx reuse`

Return the latest reusable successful strategy.

Data source:

- `.ai_context_engine/strategy_memory/strategies.jsonl`

Example:

```bash
aictx reuse --repo .
```

Example output:

```json
{"task_type": "", "entry_points": [], "files_used": [], "source": "none"}
```

### `aictx report real-usage`

Aggregate real execution logs and feedback.

Data sources:

- `.ai_context_engine/metrics/execution_logs.jsonl`
- `.ai_context_engine/metrics/execution_feedback.jsonl`

Example:

```bash
aictx report real-usage --repo .
```

Example output:

```json
{"total_executions": 0, "avg_execution_time_ms": null, "avg_files_opened": null, "avg_reopened_files": null, "strategy_usage": 0, "packet_usage": 0, "redundant_exploration_cases": 0}
```

## Internal/runtime commands

`aictx` still contains internal commands used by middleware and runner integrations, such as:

- `aictx execution prepare`
- `aictx execution finalize`
- `aictx internal run-execution`

These exist because the runtime itself depends on them, but they are not the main public surface for v1.

## Agent usage pattern

The repo-level instructions written by `aictx init` tell the agent to:

- run `aictx suggest --repo .` before opening many files
- run `aictx reflect --repo .` if it reopens the same file
- run `aictx reuse --repo .` for similar prior tasks
- run `aictx suggest --repo .` when unsure about the next step

## Historical note

Synthetic benchmark material is no longer part of the product path.

Historical reference only:

- `experiments/simulated/benchmark.py`
- `experiments/simulated/BENCHMARK_QUICKSTART.md`

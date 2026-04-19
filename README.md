# aictx

aictx is a repo-local runtime layer for coding agents.

It records real execution, stores reusable patterns, and reuses successful strategies in later executions.

## Quick start

```bash
pip install aictx
aictx install
cd your-repo
aictx init
```

## Public CLI

```bash
aictx install
aictx init
aictx suggest
aictx reflect
aictx reuse
aictx report real-usage
```

## What aictx does

- records real execution in `.ai_context_engine/metrics/execution_logs.jsonl`
- writes operational feedback in `.ai_context_engine/metrics/execution_feedback.jsonl`
- stores successful and failed strategies in `.ai_context_engine/strategy_memory/strategies.jsonl`
- reuses only successful strategies during later executions
- exposes small JSON commands for agent guidance

## What aictx does NOT do

aictx does not optimize your agent.
aictx does not guarantee better performance.

It makes past executions reusable and observable.

## Runtime loop

1. `prepare_execution()` loads prior successful strategies and may attach `execution_hint`
2. the agent executes
3. `finalize_execution()` logs real execution, stores strategy data, and writes feedback
4. the next execution can reuse successful strategies and ignore failed ones

## Main runtime artifacts

```text
.ai_context_engine/
  metrics/
    execution_logs.jsonl
    execution_feedback.jsonl
  strategy_memory/
    strategies.jsonl
```

## Command behavior

### `aictx suggest`
Returns the latest reusable strategy as next-step guidance.

### `aictx reflect`
Reads the latest execution log and returns one of:
- `looping_on_same_files`
- `too_much_exploration`
- `none`

### `aictx reuse`
Returns the latest successful strategy for reuse.

### `aictx report real-usage`
Aggregates only real execution logs and feedback.

## Notes

- file tracking depends on explicit input from the agent/runtime
- strategy reuse is simple: latest successful strategy by task type
- failed strategies are stored but never reused as hints
- no synthetic benchmarks or estimated improvements are reported

## Read next

- [Usage](docs/USAGE.md)
- [Demo](docs/DEMO.md)
- [Limitations](docs/LIMITATIONS.md)

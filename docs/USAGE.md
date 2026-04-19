# Usage

## Install and initialize

```bash
pip install aictx
aictx install
aictx init
```

## Public commands

```bash
aictx install
aictx init
aictx suggest
aictx reflect
aictx reuse
aictx report real-usage
```

## `aictx suggest`
Source: `.ai_context_engine/strategy_memory/strategies.jsonl`

Returns deterministic guidance from the latest successful strategy.

## `aictx reflect`
Source: `.ai_context_engine/metrics/execution_logs.jsonl`

Rules:
- if `len(files_reopened) > 2` -> `looping_on_same_files`
- elif `len(files_opened) > 8` -> `too_much_exploration`
- else -> `none`

## `aictx reuse`
Source: `.ai_context_engine/strategy_memory/strategies.jsonl`

Returns the latest successful strategy. Failed strategies are not reused.

## `aictx report real-usage`
Sources:
- `.ai_context_engine/metrics/execution_logs.jsonl`
- `.ai_context_engine/metrics/execution_feedback.jsonl`

Returns aggregated real usage only.

## Internal commands

Internal runtime commands exist under `aictx internal ...`, including execution prepare/finalize and wrapped execution helpers.

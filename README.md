# aictx

aictx is an execution-memory runtime for coding agents.

It records real execution, stores reusable patterns, and reuses successful strategies in later executions inside the same repository.

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
aictx clean
aictx uninstall
```

## What aictx does

- records real execution in `.ai_context_engine/metrics/execution_logs.jsonl`
- writes operational feedback in `.ai_context_engine/metrics/execution_feedback.jsonl`
- stores successful and failed strategies in `.ai_context_engine/strategy_memory/strategies.jsonl`
- reuses only successful strategies during later executions
- exposes small JSON commands for runtime guidance

## What aictx does NOT do

aictx does not optimize your agent.
aictx does not guarantee better performance.

It makes past executions observable and reusable.

## Runtime loop

1. `prepare_execution()` loads prior successful strategies and may attach `execution_hint`
2. the agent executes
3. `finalize_execution()` records logs, feedback, and strategy memory
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

## Notes

- file tracking depends on explicit input from the agent/runtime
- strategy reuse is intentionally simple: latest successful strategy by task type
- failed strategies are stored but never reused as hints
- no synthetic benchmarks or estimated improvements are reported

## Read next

- [Usage](docs/USAGE.md)
- [Demo](docs/DEMO.md)
- [Limitations](docs/LIMITATIONS.md)

## Cleanup

- `aictx clean` removes only AICTX-managed content from the current repository: the `.ai_context_engine/` scaffold, AICTX blocks in `AGENTS.md` / `AGENTS.override.md` / `CLAUDE.md`, AICTX Claude hooks/settings, and the `.gitignore` entry added by AICTX.
- `aictx uninstall` removes AICTX-managed content from all registered repositories and removes global AICTX state under `~/.ai_context_engine`, plus AICTX-managed Codex global instructions/config lines.
- Both commands are conservative: they only remove content that AICTX created or marked as AICTX-managed.

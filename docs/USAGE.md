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
aictx clean
aictx uninstall
```

After `aictx init`, manual `aictx` usage is optional. Agents are expected to follow the generated runtime instructions.

Normal intended flow:
- user runs `install` and `init`
- agent works normally inside the repo
- agent or user calls the other commands only when needed

## Output shape

Public operational commands return deterministic JSON so they can be consumed safely by:
- agents
- scripts
- CI/demo flows

This applies in particular to:
- `suggest`
- `reflect`
- `reuse`
- `report real-usage`
- `clean`
- `uninstall`

## `aictx suggest`
Source: `.ai_context_engine/strategy_memory/strategies.jsonl`

Returns deterministic guidance from the selected reusable successful strategy.

## `aictx reflect`
Source: `.ai_context_engine/metrics/execution_logs.jsonl`

Rules:
- if `len(files_reopened) > 2` -> `looping_on_same_files`
- elif `len(files_opened) > 8` -> `too_much_exploration`
- else -> `none`

## `aictx reuse`
Source: `.ai_context_engine/strategy_memory/strategies.jsonl`

Returns the selected reusable successful strategy. Failed strategies are not reused.

## Failure handling

Failed executions are persisted for history/debugging too.

Current behavior:
- successful strategies can be reused
- failed strategies stay visible in history
- failed strategies are excluded from reuse by default

## `aictx report real-usage`
Sources:
- `.ai_context_engine/metrics/execution_logs.jsonl`
- `.ai_context_engine/metrics/execution_feedback.jsonl`

Returns aggregated real usage only.

## Internal commands

Internal runtime commands exist under `aictx internal ...`, including execution prepare/finalize and wrapped execution helpers.

Important runtime output behavior:
- `aictx internal execution finalize` returns `agent_summary` and `agent_summary_text` in JSON.
- agents must append `agent_summary_text` verbatim to the final user response after finalize.
- if finalize output is unavailable, agents must say `AICTX summary unavailable`.
- `aictx internal run-execution --json` returns the full wrapped outcome as JSON.
- `aictx internal run-execution` without `--json` prints the wrapped command output plus the AICTX summary text.


## Cleanup

### Clean one repository

```bash
aictx clean --repo .
```

Removes only AICTX-managed repository content:
- `.ai_context_engine/`
- AICTX blocks inside `AGENTS.md`, `AGENTS.override.md`, and `CLAUDE.md`
- AICTX Claude hook files and matching entries in `.claude/settings.json`
- the `.gitignore` line for `.ai_context_engine/`

### Uninstall globally

```bash
aictx uninstall
```

Removes only AICTX-managed global content:
- `~/.ai_context_engine/`
- AICTX block in `~/.codex/AGENTS.override.md`
- AICTX-managed fallback line in `~/.codex/config.toml`
- AICTX-managed content from registered repositories

Both commands return JSON with the exact files they removed or updated.

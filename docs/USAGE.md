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

Public contract:
- `install`, `init`, `suggest`, `reflect`, `reuse`, `report real-usage`, `clean`, `uninstall`
- these are the supported user-facing commands
- outputs are deterministic JSON where applicable

Internal contract:
- `aictx internal ...`
- used by middleware, wrappers, hooks, and runner integrations
- internal commands are runtime plumbing, not the main public UX

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
Source: `.aictx/strategy_memory/strategies.jsonl`

Returns deterministic guidance from the selected reusable successful strategy.

## `aictx reflect`
Source: `.aictx/metrics/execution_logs.jsonl`

Rules:
- if `len(files_reopened) > 2` -> `looping_on_same_files`
- elif `len(files_opened) > 8` -> `too_much_exploration`
- else -> `none`

## `aictx reuse`
Source: `.aictx/strategy_memory/strategies.jsonl`

Returns the selected reusable successful strategy. Failed strategies are not reused.

## Failure handling

Failed executions are persisted for history/debugging too.

Current behavior:
- successful strategies can be reused
- failed strategies stay visible in history
- failed strategies are excluded from reuse by default

## `aictx report real-usage`
Sources:
- `.aictx/metrics/execution_logs.jsonl`
- `.aictx/metrics/execution_feedback.jsonl`
- `.aictx/continuity/continuity_metrics.json` when present

Returns aggregated real usage only.

## Continuity artifacts

Primary continuity paths are repo-local:

```text
.aictx/continuity/session.json
.aictx/continuity/handoff.json
.aictx/continuity/decisions.jsonl
.aictx/continuity/semantic_repo.json
.aictx/continuity/dedupe_report.json
.aictx/continuity/staleness.json
.aictx/continuity/continuity_metrics.json
```

Related runtime paths:

```text
.aictx/strategy_memory/strategies.jsonl
.aictx/failure_memory/failure_patterns.jsonl
.aictx/metrics/execution_logs.jsonl
.aictx/metrics/execution_feedback.jsonl
```

These files stay inside the repository. Cross-project behavior must come from workspace registry/config, not hardcoded machine paths.

## Internal commands

Internal runtime commands exist under `aictx internal ...`, including execution prepare/finalize and wrapped execution helpers.

Important runtime output behavior:
- `aictx internal execution finalize` returns `agent_summary` and `agent_summary_text` in JSON.
- agents must append `agent_summary_text` verbatim to the final user response after finalize.
- if finalize output is unavailable, agents must say `AICTX summary unavailable`.
- `aictx internal run-execution --json` returns the full wrapped outcome as JSON.
- `aictx internal run-execution` without `--json` prints the wrapped command output plus the AICTX summary text.

Important boundary:
- public docs should point users to the public CLI first
- internal commands are for agent/runtime cooperation and integration authors
- correctness still depends on the runner and agent actually calling prepare/finalize and respecting repo instructions


## Cleanup

### Clean one repository

```bash
aictx clean --repo .
```

Removes only AICTX-managed repository content:
- `.aictx/`
- AICTX blocks inside `AGENTS.md` and `CLAUDE.md`
- legacy AICTX content inside `AGENTS.override.md` when present
- AICTX Claude hook files and matching entries in `.claude/settings.json`
- the `.gitignore` line for `.aictx/`

### Uninstall globally

```bash
aictx uninstall
```

Removes only AICTX-managed global content:
- `~/.aictx/`
- AICTX block in `~/.codex/AGENTS.override.md`
- AICTX-managed fallback line in `~/.codex/config.toml`
- AICTX-managed content from registered repositories

Both commands return JSON with the exact files they removed or updated.

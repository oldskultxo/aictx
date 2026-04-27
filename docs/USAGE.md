# Usage

## Install and initialize

```bash
pip install aictx
aictx install
aictx init --repo .
```

## Public commands

```bash
aictx install
aictx init
aictx suggest
aictx reflect
aictx reuse
aictx next
aictx task start "Fix login token refresh"
aictx task status --json
aictx task list --json
aictx task show fix-login-token-refresh --json
aictx task update --json-patch '{"next_action":"run targeted auth tests"}' --json
aictx task resume fix-login-token-refresh --json
aictx task close --status resolved --json
aictx map status
aictx map refresh
aictx map query "startup banner"
aictx report real-usage
aictx clean --repo .
aictx uninstall
```

Public contract:

- `install`, `init`, `suggest`, `reflect`, `reuse`, `next`, `task ...`, `map ...`, `report real-usage`, `clean`, `uninstall`
- these are the supported user-facing commands
- outputs are deterministic JSON where applicable

Internal contract:

- `aictx internal ...`
- used by middleware, wrappers, hooks, and runner integrations
- internal commands are runtime plumbing, not the main user UX

After `aictx init`, manual `aictx` usage is optional.
Agents are expected to follow the generated runtime instructions.

## Output shape

Operational commands are designed to be scriptable and deterministic.
This is especially true for:

- `suggest`
- `reflect`
- `reuse`
- `next --json`
- `task status --json`
- `report real-usage`
- `clean`
- `uninstall`

## `aictx suggest`

Source: `.aictx/strategy_memory/strategies.jsonl`

Returns deterministic guidance from the selected reusable successful strategy.
Optional ranking context can include request text, files, commands, tests, and notable errors.

## `aictx reflect`

Source: latest execution logs

Current rules stay intentionally simple:

- many reopened files -> possible loop
- many opened files -> too much exploration
- otherwise -> no issue

Output includes fields such as:

- `possible_issue`
- `reopened_files`
- `opened_files_count`
- `suggested_next_action`
- `recommended_entry_points`
- `reason`

## `aictx reuse`

Source: `.aictx/strategy_memory/strategies.jsonl`

Returns the latest reusable successful strategy.
Failed strategies are not reused.

## `aictx next`

Shows compact actionable continuity guidance.

Examples:

```bash
aictx next --repo .
aictx next --repo . --request "startup banner"
aictx next --repo . --json
```

`--json` returns the structured continuity brief and `why_loaded` evidence.

When an active Work State exists, `aictx next` prioritizes it before older handoff/decision/reuse context. When no task is active, it may show the most recent paused or blocked task as secondary context.

## `aictx task ...`

Manages repo-local active Work State.

Examples:

```bash
aictx task start "Fix login token refresh" --repo . --json
aictx task status --repo . --json
aictx task list --repo . --json
aictx task show fix-login-token-refresh --repo . --json
aictx task update --repo . --json-patch '{"current_hypothesis":"token not persisted before retry","next_action":"inspect auth interceptor ordering"}' --json
aictx task update --repo . --from-file work-state-patch.json --json
aictx task resume fix-login-token-refresh --repo . --json
aictx task close --repo . --status resolved --json
aictx task close --repo . --status blocked --json-patch '{"risks":["waiting on flaky CI"],"next_action":"rerun CI"}' --json
```

Current subcommands:

- `task start` -> create/update `.aictx/tasks/active.json`, create `threads/<task-id>.json`, append `started` event
- `task status` -> return the active task, or `{ "active": false }` when none exists
- `task status --all` / `task list` -> list stored task threads
- `task show <task-id>` -> inspect a specific stored task thread
- `task update` -> merge supported fields into the active task and append `updated` event; accepts `--json-patch` or `--from-file`
- `task update --json` -> returns the normalized state plus `updated: true` and `changed_fields`
- `task resume <task-id>` -> make a stored task active again and append `resumed` event
- `task close` -> mark `resolved|abandoned|blocked|paused`, clear active pointer, keep thread history
- `task close --json-patch ...` -> merge a final factual patch while closing

See `docs/WORK_STATE.md` for artifact shape and limits.

## `aictx map ...`

RepoMap is optional.

Examples:

```bash
aictx map status --repo .
aictx map refresh --repo .
aictx map query --repo . "startup banner"
```

Optional setup:

```bash
pip install "aictx[repomap]"
aictx install --with-repomap
aictx init --repo .
```

## `aictx report real-usage`

Sources:

- `.aictx/metrics/execution_logs.jsonl`
- `.aictx/metrics/execution_feedback.jsonl`
- `.aictx/continuity/continuity_metrics.json` when present

Current report may include:

- strategy and packet usage
- redundant exploration counts
- capture coverage
- failure pattern counts
- structured error capture metrics: event counts, toolchains seen, top phases/toolchains, and failure patterns with events
- continuity health signals
- RepoMap status snapshot
- active Work State visibility: `active`, `task_id`, `status`, `threads_count`, `last_updated_at`, `recent_statuses`

## Continuity artifacts

Primary continuity paths are repo-local:

```text
.aictx/continuity/session.json
.aictx/continuity/handoff.json
.aictx/continuity/handoffs.jsonl
.aictx/continuity/decisions.jsonl
.aictx/continuity/semantic_repo.json
.aictx/continuity/dedupe_report.json
.aictx/continuity/staleness.json
.aictx/continuity/continuity_metrics.json
.aictx/continuity/last_execution_summary.md
.aictx/tasks/active.json
.aictx/tasks/threads/<task-id>.json
.aictx/tasks/threads/<task-id>.events.jsonl
```

Related runtime paths:

```text
.aictx/strategy_memory/strategies.jsonl
.aictx/failure_memory/failure_patterns.jsonl
.aictx/area_memory/areas.json
.aictx/metrics/execution_logs.jsonl
.aictx/metrics/execution_feedback.jsonl
```

These files stay inside the repository.
Cross-project behavior must come from workspace registry/config, not hardcoded machine paths.

## Failure-aware execution

Wrapped execution can capture structured error events automatically:

```bash
aictx internal run-execution \
  --repo . \
  --request "run tests" \
  --agent-id demo \
  --json \
  -- python -m pytest -q
```

When the wrapped command fails, the JSON outcome may include `execution_observation.error_events`, derived `notable_errors`, and a persisted failure pattern. Later `prepare_execution` calls can load related patterns so the next agent sees prior failure context.

Explicit integrations can also pass `--error-event-json` to `internal execution prepare`, `internal execution finalize`, or `internal run-execution`.

## Internal commands

Internal runtime commands exist under `aictx internal ...`, including execution prepare/finalize and wrapped execution helpers.

Important runtime behavior:

- `aictx internal execution finalize` returns `agent_summary` and `agent_summary_text`
- `agent_summary_text` is the canonical factual source for the final AICTX summary
- agents may localize or lightly humanize that summary when policy allows, but must preserve facts
- if finalize output is unavailable, agents must say `AICTX summary unavailable`
- `prepare_execution` may return `startup_banner_text`, shown once per visible session when the runtime requires it
- `prepare_execution` can expose `active_work_state` when `.aictx/tasks/active.json` points to a valid task thread
- `finalize` can expose prepared/final/effective task and area classification values
- `finalize` can conservatively update active Work State when factual execution evidence or explicit `--work-state-json` / `--work-state-file` is provided
- `aictx internal run-execution --json` returns the full wrapped outcome as JSON, including structured `error_events` when captured
- `aictx internal run-execution` without `--json` prints command output plus runtime banner/summary text when applicable

## Cleanup

### Clean one repository

```bash
aictx clean --repo .
```

Removes AICTX-managed content from that repository only.

### Uninstall globally

```bash
aictx uninstall
```

Removes AICTX-managed global content and registered repo content.

Both commands return JSON describing the exact files removed or updated.

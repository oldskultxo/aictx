# Technical overview

AICTX is a repo-local continuity runtime for coding agents.

It is not an agent, planner, dashboard, vector database, or hidden memory service. It stores execution evidence and continuity artifacts inside the repository so later agent sessions can resume with context.

This document is the technical map of the system.

---

## What AICTX is technically

AICTX is composed of:

- repo scaffold and managed instruction files;
- runner integrations for Codex, Claude, and generic agents;
- internal runtime commands used by agents/hooks;
- public CLI commands used for setup, inspection, and debugging;
- middleware around prepare/finalize execution;
- repo-local continuity artifacts;
- active Work State runtime;
- failure, strategy, area, and semantic continuity memories;
- optional RepoMap structural index;
- cleanup/uninstall machinery.

The user-facing experience is simple:

```text
install -> init -> use your coding agent
```

The technical runtime underneath is:

```text
boot -> prepare -> execution -> finalize -> persist continuity -> next session
```

---

## System components

| Component | Responsibility |
|---|---|
| Repo scaffold | Creates `.aictx/` and managed runner files |
| Runner integrations | Writes `AGENTS.md`, `CLAUDE.md`, and Claude hook configuration |
| Internal runtime CLI | Provides `boot`, `prepare`, `finalize`, and `run-execution` |
| Public CLI | Provides install/init/next/task/map/report/cleanup commands |
| Middleware | Loads continuity before work and records evidence after work |
| Work State | Stores active suspended task state |
| Failure Memory | Stores observed failure patterns |
| Strategy Memory | Stores successful reusable execution patterns |
| Area Memory | Groups signals by repo area |
| RepoMap | Optional structural file/symbol lookup |
| Execution Summary | Produces factual final runtime output |
| Cleanup | Removes managed repo/global content |

---

## Runtime lifecycle

### 1. Install

`aictx install` prepares global/runtime state.

It may configure:

- workspace id/root;
- cross-project mode;
- optional global Codex files;
- optional RepoMap request;
- AICTX home/config state.

It should not be confused with repo initialization.

### 2. Init

`aictx init` prepares one repository.

It can:

- create/preserve `.aictx/`;
- prepare repo runtime state;
- install repo runner integrations;
- write `AGENTS.md`;
- write `CLAUDE.md`;
- write `.claude/settings.json`;
- write `.claude/hooks/*`;
- persist repo communication mode;
- initialize RepoMap if requested and available;
- register the repo unless disabled;
- optionally switch the AICTX-managed `.gitignore` block between local-only and git-portable continuity without moving canonical artifacts.

### 3. Boot runtime state

Runner integrations or advanced users may call:

```bash
aictx internal boot --repo .
```

`internal boot` loads bootstrap/runtime state and prints a diagnostic payload, including effective preferences, communication policy, model routing, task/failure/memory graph status, repo bootstrap state, and consistency checks.

It is not the same thing as the user-visible startup continuity banner.

### 4. Prepare execution

Before meaningful work, integrations can call:

```bash
aictx internal execution prepare ...
```

`prepare_execution()` loads bounded continuity context and can return the user-visible startup continuity payload, including `startup_banner_text`, `startup_banner_policy`, session identity, continuity brief, active Work State, and skipped Work State details.

### 5. Agent execution

The agent works normally. It can inspect public AICTX surfaces when useful:

```bash
aictx next --json
aictx map query "..."
aictx task status --json
```

### 6. Finalize execution

After work, integrations can call:

```bash
aictx internal execution finalize ...
```

`finalize_execution()` stores observed evidence and returns `agent_summary_text`,
the compact user-facing final summary.

### 7. Next session

The next session can load continuity from repo-local artifacts instead of starting from scratch.

---

## Public CLI vs internal runtime

### Public CLI

Human-facing and advanced integration commands:

```bash
aictx install
aictx init
aictx next
aictx task ...
aictx map ...
aictx report real-usage
aictx clean
aictx uninstall
```

These are for setup, inspection, explicit control, debugging, demos, and cleanup.

### Internal runtime CLI

Agent/hook-facing commands:

```bash
aictx internal boot --repo .
aictx internal execution prepare ...
aictx internal execution finalize ...
aictx internal run-execution ...
```

These are the runtime contract. Supported agents should use them automatically through repo instructions or hooks.

Important distinction:

```text
internal boot = bootstrap/runtime diagnostic payload.
prepare_execution startup_banner_text = user-visible startup continuity banner.
```

---

## Agent integration model

AICTX is runner-aware, not runner-locked.

### Codex-first

Codex support uses:

- `AGENTS.md`;
- optional global Codex files through `aictx install --install-codex-global`;
- model instruction fallback files;
- the same CLI/runtime contract.

### Claude-aware

Claude support uses:

- `CLAUDE.md`;
- `.claude/settings.json`;
- `.claude/hooks/aictx_session_start.py`;
- `.claude/hooks/aictx_user_prompt_submit.py`;
- `.claude/hooks/aictx_pre_tool_use.py`.

### Generic fallback

Generic agents use:

- repo instructions;
- public inspection commands;
- internal prepare/finalize/run-execution commands;
- JSON/Markdown outputs.

---

## Startup continuity and session identity

Startup identity is based on session context.

The visible startup continuity banner is produced through prepare/startup continuity, not by the raw `internal boot` diagnostic payload.

The canonical runtime banner header shape is:

```text
<agent_label> · session #<n> · awake
```

Typical labels:

```text
codex@repo-name
claude@repo-name
agent@repo-name
```

The banner is a compact resumption card. It can include:

- `Resuming: ...`
- `Last progress: ...` or `Blocked: ...`
- `Next: ...`
- `Active task: ... Next: ...`

The runtime canonical banner is English. Agents may localize labels and connective wording to the current user language, but must preserve facts, structure, file paths, commands, flags, test names, package names, and code identifiers.

Example:

```text
codex@aictx · session #40 · awake

Resuming: branch-safe Work State finalize behavior.
Last progress: finalize behavior aligned with tests.
Next: tests/test_work_state_runtime.py
Active task: Improve public docs. Next: update installation guide.
```

---

## Boot payload vs startup banner

These two surfaces are related but different.

### `aictx internal boot --repo .`

Boot is a runtime/bootstrap diagnostic surface. It can print:

- ASCII banner;
- boot summary;
- user defaults;
- effective preferences;
- communication policy;
- project registry;
- model routing;
- cost optimizer status;
- task memory status;
- failure memory status;
- memory graph status;
- consistency checks;
- repo bootstrap state.

It is useful for diagnostics and runtime verification.

### `startup_banner_text`

The visible agent startup banner is the compact continuity message intended for the user. It is surfaced through prepare/startup continuity and should be rendered by the agent at the start of the first visible response when policy says so.

Example shape:

```text
codex@repo · session #40 · awake

Resuming: previous work.
Last progress: aligned runtime behavior with tests.
Next: tests/test_smoke.py
```

---

## Handoffs and Decisions

Handoffs and Decisions are first-class continuity concepts. See [Handoffs and Decisions](HANDOFFS.md).

They preserve:

- how the previous execution ended;
- recommended starting points;
- explicit project or architecture decisions;
- compact semantic repo continuity.

They differ from Work State:

```text
Work State = current suspended task state.
Handoff = how the previous execution ended.
Decision = explicit project/architecture fact.
```

---

## Continuity artifact model

Primary continuity artifacts:

```text
.aictx/continuity/session.json
.aictx/continuity/handoff.json
.aictx/continuity/handoffs.jsonl
.aictx/continuity/decisions.jsonl
.aictx/continuity/semantic_repo.json
.aictx/continuity/dedupe_report.json
.aictx/continuity/staleness.json
.aictx/continuity/continuity_metrics.json
.aictx/tasks/active.json
.aictx/tasks/threads/<task-id>.json
.aictx/tasks/threads/<task-id>.events.jsonl
.aictx/strategy_memory/strategies.jsonl
.aictx/failure_memory/failure_patterns.jsonl
.aictx/area_memory/areas.json
.aictx/metrics/execution_logs.jsonl
.aictx/metrics/execution_feedback.jsonl
```

Optional/latest-run artifacts:

```text
.aictx/continuity/last_execution_summary.md
.aictx/repo_map/config.json
.aictx/repo_map/manifest.json
.aictx/repo_map/index.json
.aictx/repo_map/status.json
```

---

## Capability matrix

| Capability | Main artifacts | Main consumers |
|---|---|---|
| Session identity | `session.json` | startup banner |
| Handoff | `handoff.json`, `handoffs.jsonl` | startup, next, prepare |
| Decisions | `decisions.jsonl` | prepare, next |
| Semantic repo memory | `semantic_repo.json` | prepare |
| Work State | `.aictx/tasks/*` | prepare, next, finalize |
| Branch-safe Work State | `git_context` in Work State | prepare, finalize |
| Failure Memory | `failure_patterns.jsonl` | prepare, finalize, report |
| Strategy Memory | `strategies.jsonl` | suggest, reuse, prepare |
| Area Memory | `areas.json` | strategy/failure/report |
| RepoMap | `.aictx/repo_map/*` | map commands, prepare |
| Execution Summary | `agent_summary_text`, `last_execution_summary.md` | final response, next session |
| Real usage report | metrics/memory artifacts | `report real-usage` |
| Runner integrations | `AGENTS.md`, `CLAUDE.md`, `.claude/*` | Codex, Claude, generic agents |
| Cleanup | managed blocks, registry, global files | `clean`, `uninstall` |

---

## Work State runtime

Work State preserves active task state:

- goal;
- current hypothesis;
- active files;
- verified items;
- unverified assumptions;
- discarded paths;
- next action;
- recommended commands;
- risks;
- uncertainties;
- source execution ids.

It lives under:

```text
.aictx/tasks/active.json
.aictx/tasks/threads/<task-id>.json
.aictx/tasks/threads/<task-id>.events.jsonl
```

It can be updated by:

- public `aictx task ...` commands;
- explicit runtime payloads;
- conservative finalize evidence.

It does not infer hidden intent from sparse signals.

---

## Branch-safe Work State loading

When saved in a git repo, Work State includes git context:

```text
available
branch
head
dirty
changed_files
captured_at
```

Evaluation outcomes include:

```text
no_git_context
git_unavailable
same_branch
branch_changed_but_merged
branch_mismatch_unmerged
dirty_branch_mismatch
```

Core rule:

```bash
git merge-base --is-ancestor <saved_head> HEAD
```

Loading behavior:

| Situation | Behavior |
|---|---|
| no git context | load conservatively |
| git unavailable | load conservatively with warning |
| same branch | load |
| same branch, changed HEAD | load with warning |
| branch changed, saved commit is ancestor of current HEAD | load with warning |
| branch changed, saved commit is not ancestor | skip |
| saved state dirty and branch changed | skip |

Finalize must not update a Work State that prepare skipped for unsafe branch mismatch.

---

## Failure Memory and error events

Failure Memory stores observed failures as structured patterns.

Structured error events can include:

```text
toolchain
phase
severity
message
code
file
line
command
exit_code
fingerprint
```

Recognized families include:

```text
Python / pytest
mypy / ruff / pyright
npm
TypeScript
ESLint
Jest / Vitest
Go
Rust / Cargo
Java / Maven
.NET
C / C++
Ruby
PHP
generic unknown failures
```

Failure Memory can help later sessions recognize repeated failures, avoid ineffective paths, and connect later successful work to prior failure context.

Failed strategies are not reused as positive strategy hints.

---

## Strategy Memory

Strategy Memory stores successful execution patterns. See [Strategy Memory](STRATEGY_MEMORY.md) for the dedicated concept page.

It can consider:

- task type;
- prompt similarity;
- overlapping files;
- primary entry point;
- commands/tests/errors;
- area id;
- recency;
- observed execution evidence.

Failed strategies are retained for history/debugging but excluded from positive reuse.

---

## Area Memory

Area Memory groups observed facts by repo area.

It can influence:

- continuity loading;
- strategy selection;
- failure lookup;
- report visibility.

Area ids are path-derived and deterministic. They are hints, not semantic proof.

---

## RepoMap

RepoMap is optional and Tree-sitter based.

Commands:

```bash
aictx map status
aictx map refresh
aictx map query "..."
```

Artifacts:

```text
.aictx/repo_map/config.json
.aictx/repo_map/manifest.json
.aictx/repo_map/index.json
.aictx/repo_map/status.json
```

RepoMap provides structural hints. It is not semantic understanding and is not required for core continuity.

---

## Execution Summary

`finalize_execution()` returns:

```text
agent_summary
agent_summary_text
```

The detailed latest summary may be written to:

```text
.aictx/continuity/last_execution_summary.md
```

Agents should treat `agent_summary_text` as the canonical compact user-facing
final summary source. `.aictx/continuity/last_execution_summary.md` is the
detailed diagnostic latest-run summary and should remain linked from the final
summary when generated.

If finalize output is unavailable, the agent should say:

```text
AICTX summary unavailable
```

---

## Real usage report

`aictx report real-usage` builds a descriptive report from repo-local artifacts.

It may include:

- strategy usage;
- context/packet usage;
- capture coverage;
- failure counts;
- error event metrics;
- continuity health;
- Work State visibility;
- RepoMap status.

It is not a benchmark and does not prove productivity/token savings.

---

## Cleanup and uninstall

`aictx clean --repo .` removes repo-local AICTX-managed state and unregisters the repo.

It may remove or update:

- `.aictx/`;
- AICTX Claude hooks;
- AICTX-managed blocks in `AGENTS.md`, `CLAUDE.md`, `AGENTS.override.md`;
- AICTX entries in `.claude/settings.json`;
- AICTX `.gitignore` entries.

`aictx uninstall` can also clean registered repos/workspaces, global Codex managed files/config, and the global AICTX home.

See [Cleanup](CLEANUP.md).

---

## Deterministic vs heuristic behavior

Deterministic:

- artifact paths;
- schema fields;
- branch-safe loading rules;
- CLI contracts;
- managed block markers;
- cleanup target classes;
- no hidden memory claims.

Heuristic:

- task type inference;
- area derivation;
- strategy ranking;
- failure similarity;
- RepoMap query scoring;
- next-action usefulness.

Heuristic outputs should remain bounded and explainable.

---

## Limits

AICTX depends on agent/integration cooperation.

If an agent does not call prepare/finalize or pass observed facts, AICTX cannot record them.

AICTX does not:

- guarantee correctness;
- guarantee speedups;
- guarantee token savings;
- replace review;
- autonomously repair the repo;
- infer facts that were not observed.


---

## Documentation map

Product and setup:

- [README](../README.md)
- [Installation](INSTALLATION.md)
- [Quickstart](QUICKSTART.md)

Core runtime concepts:

- [Work State](WORK_STATE.md)
- [RepoMap](REPOMAP.md)
- [Failure Memory](FAILURE_MEMORY.md)
- [Strategy Memory](STRATEGY_MEMORY.md)
- [Handoffs and Decisions](HANDOFFS.md)
- [Execution Summary](EXECUTION_SUMMARY.md)

Operations and trust:

- [Usage](USAGE.md)
- [Cleanup](CLEANUP.md)
- [Safety](SAFETY.md)
- [Limitations](LIMITATIONS.md)
- [Upgrade](UPGRADE.md)

# aictx

AICTX is a repo-local continuity runtime for coding agents.

It helps each new session behave like the same repo-native engineer continuing prior work.

Current documented implementation: `4.5.1`

---

## Why this exists

Most agent workflows start from scratch every time.

aictx allows them to reuse what already worked.

---

## What aictx is

A repo-local continuity runtime for coding agents.

It records real execution, preserves continuity artifacts inside the repository, and reuses successful strategies in later executions.

- repo-local continuity runtime
- real execution logging
- reusable strategy memory
- canonical handoff, decisions, semantic repo, staleness, and continuity metrics artifacts
- structured execution signal capture with provenance
- toolchain-aware error capture and failure memory
- failure and repo-area memory
- lightweight runtime guidance and post-task summaries for coding agents
- optional RepoMap structural lookup when Tree-sitter support is installed

---

## Safety model

AICTX modifies repository files and can optionally install runner integrations.
By default it creates repo-local runtime artifacts only during repo setup, and `aictx install` does not modify global Codex files.
Global Codex integration requires `aictx install --install-codex-global`.

---

## Quick start

```bash
pip install aictx
aictx install
cd your-repo
aictx init --repo .
```

After `aictx init`, you can use your coding agent normally in that repo.

Manual `aictx` commands after initialization are optional:
- the intended flow is `install` + `init`, then agent-driven usage
- `suggest`, `reflect`, `reuse`, `next`, `task ...`, and `report real-usage` remain available for inspection, debugging, or manual control
- Claude/Codex integration files and hooks added by `init` are there to help the agent use `aictx` automatically when the runner respects repo instructions

---

## Public CLI

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
aictx task update --from-file work-state-patch.json --json
aictx task resume fix-login-token-refresh --json
aictx task close --status resolved --json
aictx map status
aictx map refresh
aictx map query "startup banner"
aictx report real-usage
aictx clean --repo .
aictx uninstall
```

Only `install` and `init` are part of the normal setup path.

The rest of the public commands are optional operational commands:
- `suggest`, `reflect`, `reuse` -> for manual inspection or explicit agent calls
- `next`, `task ...`, `map status|refresh|query` -> for compact continuity, active work preservation, and RepoMap structural lookup operations
- `report real-usage` -> for reviewing stored execution data
- `clean`, `uninstall` -> for removing AICTX-managed content

---

## RepoMap (optional)

RepoMap is an optional Tree-sitter powered structural index.
It helps AICTX suggest likely files/symbols.
It does not guarantee speed or token savings.

Setup and usage:

```bash
pip install "aictx[repomap]"
aictx install --with-repomap
aictx init --repo .
aictx map status
aictx map query "startup banner"
```

---

## What aictx does

* records real execution in `.aictx/metrics/execution_logs.jsonl`
* writes operational feedback in `.aictx/metrics/execution_feedback.jsonl`
* stores successful and failed strategies in `.aictx/strategy_memory/strategies.jsonl`
* stores continuity artifacts in `.aictx/continuity/`
  * `session.json`
  * `handoff.json`
  * `handoffs.jsonl` (rolling recent handoff history)
  * `decisions.jsonl`
  * `semantic_repo.json`
  * `dedupe_report.json`
  * `staleness.json`
  * `continuity_metrics.json`
  * `last_execution_summary.md` (latest detailed finalize summary)
* stores active task continuity in `.aictx/tasks/`
  * `active.json`
  * `threads/<task-id>.json`
  * `threads/<task-id>.events.jsonl`
* captures available files, commands, tests, and errors with provenance instead of inventing data
* normalizes command/test/lint/type/build/compile failures into compact `error_events` with `toolchain`, `phase`, `code`, path, line, command, exit code, and fingerprint when observed
* derives backward-compatible `notable_errors` from structured error events when possible
* preserves provisional and observed classification for continuity traceability (`prepared_*`, `final_*`, `effective_*`)
* stores repo-local failure patterns and area memory for later debugging/context
* reuses only successful strategies during later executions
* loads related failure patterns during prepare so agents can avoid repeating known mistakes
* distinguishes new, repeated, resolved, and merely considered failure context in `agent_summary_text` without inventing causality
* returns `agent_summary` and `agent_summary_text` after finalize; `agent_summary_text` is the canonical factual source for the final AICTX summary
* can preserve active Work State across sessions: goal, current hypothesis, active files, next action, factual verified items, and conservative recommended commands
* exposes small JSON commands for runtime guidance
* does not rely on hidden model memory or opaque cross-repo state


## Failure capture and learning

AICTX 4.4 adds toolchain-aware failure capture for wrapped executions and explicit runtime signals.

When AICTX observes failed commands, tests, linting, typing, builds, or compilation, it can normalize the output into structured `error_events` with fields such as:

```text
toolchain, phase, severity, message, code, file, line, command, exit_code, fingerprint
```

Supported recognition includes Python/pytest/mypy/ruff/pyright, JavaScript and TypeScript tooling, Go, Rust/Cargo, Java/JVM, .NET, C/C++, Ruby, PHP, and a generic fallback.

The failure memory flow remains inspectable:

- structured events are persisted in `.aictx/failure_memory/failure_patterns.jsonl`
- `notable_errors` remains available as the compact backward-compatible string form
- `prepare_execution()` can load related failure patterns for the next agent
- `finalize_execution()` can record new patterns, recognize repeated patterns, or resolve prior patterns after a successful related execution
- `agent_summary_text` reports this compactly: learned new pattern, recognized existing pattern, resolved prior failure, or considered/used prior failure context without claiming avoidance unless the observed facts support it

---

## What AICTX modifies

Repo-local:
- `.aictx/`
- AICTX-managed blocks in `AGENTS.md` and `CLAUDE.md`
- `.claude/settings.json` merged AICTX hook entries
- `.claude/hooks/aictx_*.py`
- `.gitignore` entries for AICTX runtime paths

Optional global:
- `~/.codex/AGENTS.override.md`
- `~/.codex/AICTX_Codex.md`
- `~/.codex/config.toml`

Global Codex files are only updated when `--install-codex-global` is passed.

---

## Idempotency guarantees

- `aictx init` is non-destructive for existing AICTX execution logs and strategy memory
- existing `.aictx/metrics/*.jsonl` and `.aictx/strategy_memory/*.jsonl` files are preserved
- `.claude/settings.json` is merged, not overwritten
- AICTX-managed Markdown blocks and hooks are idempotent
- `aictx init` does not delete legacy non-AICTX paths

---

## What aictx does NOT do

aictx does not optimize your agent.
aictx does not guarantee better performance.

It makes past executions observable and reusable.

---

## Who this is for

- engineers using coding agents repeatedly in the same repository
- teams that want repo-local execution history and reusable strategies
- users who prefer traceable artifacts over heuristic-heavy automation

## Who this is not for

- users expecting guaranteed productivity gains
- teams looking for a full orchestration platform
- workflows that do not preserve repo-level instructions or execution discipline

---

## Runtime loop

1. `prepare_execution()` loads prior successful strategies and may attach `execution_hint`
2. it exposes `continuity_brief` with ranked, evidence-backed next context when prior memory is useful
3. for non-trivial work it may also build a bounded packet/context payload and continuity summary
4. the agent executes
5. `finalize_execution()` records logs, feedback, strategy memory, `continuity_value`, `capture_quality`, and `agent_summary_text`
6. `finalize_execution()` can also correct provisional task/area typing from observed execution evidence and expose `prepared_*`, `final_*`, and `effective_*`
7. the agent uses `agent_summary_text` as the canonical factual source for the final AICTX summary; if finalize output is unavailable, it says `AICTX summary unavailable`
8. the next execution can reuse successful strategies and ignore failed ones

---

## Artifact contract

The stable repo-local continuity artifact contract in `4.5.1` is:

```text
.aictx/continuity/session.json
.aictx/continuity/handoff.json
.aictx/continuity/decisions.jsonl
.aictx/continuity/semantic_repo.json
.aictx/continuity/dedupe_report.json
.aictx/continuity/staleness.json
.aictx/continuity/continuity_metrics.json
.aictx/strategy_memory/strategies.jsonl
.aictx/failure_memory/failure_patterns.jsonl
.aictx/metrics/execution_logs.jsonl
.aictx/metrics/execution_feedback.jsonl
.aictx/tasks/active.json
.aictx/tasks/threads/*
```

Behavior expectations:

- continuity artifacts are repo-local and inspectable
- startup loads only bounded, deterministic continuity context
- startup banner behavior is visible-session aware and shown at most once per visible session
- packet/context middleware may be built for non-trivial work and remains inspectable when present
- failed strategies remain in history but are excluded from positive reuse
- maintenance and staleness files mark or summarize; they do not imply hidden ML or automatic repair

Additional optional runtime outputs may appear:
- `.aictx/continuity/handoffs.jsonl`
- `.aictx/repo_map/config.json`
- `.aictx/repo_map/manifest.json`
- `.aictx/repo_map/index.json`
- `.aictx/repo_map/status.json`

Additional latest-run output:
- `.aictx/continuity/last_execution_summary.md`

## Main runtime artifacts

```text
.aictx/
  continuity/
    handoff.json
    handoffs.jsonl
    decisions.jsonl
    semantic_repo.json
    dedupe_report.json
    staleness.json
    continuity_metrics.json
    last_execution_summary.md
  metrics/
    execution_logs.jsonl
    execution_feedback.jsonl
  strategy_memory/
    strategies.jsonl
```

---

## Additional properties

* repo-local artifacts are the source of truth; execution history and strategy memory stay inspectable inside the repository
* failed strategies are stored, but they are excluded from reuse by default
* public operational command outputs are deterministic and machine-readable JSON; internal `run-execution` without `--json` also prints the user-facing AICTX summary
* AICTX-managed changes can be removed cleanly with `aictx clean` and `aictx uninstall`

---

## Notes

* file tracking depends on explicit input from the agent/runtime; wrapped execution can capture commands, tests, structured error events, and edited files best-effort
* strategy reuse is heuristic: matching task type, prompt similarity, overlapping files, primary entry point, commands/tests/errors, and area are preferred, with recency as a secondary signal
* `prepare` task/area typing is provisional; `finalize` can correct it from observed files, tests, commands, errors, and result summary
* continuity loading is layered: session identity, handoff, recent decisions, failure patterns, semantic repo memory, procedural reuse, maintenance hygiene, staleness filtering, and aggregate continuity metrics
* `continuity_brief` and `continuity_context.ranked_items` explain likely next paths, active decisions, known risks, recommended commands/tests, and why each memory source was loaded
* `aictx next --repo .` renders the same continuity guidance as compact human-facing output, with `--json` available for integrations
* task typing uses explicit metadata first, then deterministic keyword/path inference, then `unknown`
* capture provenance distinguishes explicit, runtime-observed, heuristic, and unknown signals
* middleware packet generation is conservative and task-dependent, not unconditional for every execution
* `reflect` is intentionally small-scope: it only looks at the latest execution log, but it can now return issue classification, counts, suggested next action, and recommended entry points
* `suggest` and `reuse` can rank with extra context such as request text, files, commands, tests, and notable errors when that context is provided
* failed strategies are stored and excluded from positive reuse hints; structured failure patterns may still inform failure-aware avoidance and debugging context
* no synthetic benchmarks or estimated improvements are reported

---

## Cleanup

* `aictx clean` removes only AICTX-managed content from the current repository: the `.aictx/` scaffold, AICTX blocks in `AGENTS.md` / `CLAUDE.md`, legacy AICTX content in `AGENTS.override.md` when present, AICTX Claude hooks/settings, and the `.gitignore` entry added by AICTX
* `aictx uninstall` removes AICTX-managed content from all registered repositories and removes global AICTX state under `~/.aictx`, plus AICTX-managed Codex global instructions/config lines
* both commands are conservative: they only remove content that AICTX created or marked as AICTX-managed

---

## Possible evolution

The current `4.5.1` runtime keeps continuity deterministic and inspectable rather than turning into an opaque agent platform.

Possible future work, based on real usage:

* better file access capture from agent/runtime integrations
* broader runner-native signal capture where supported
* more parser samples for newly observed toolchain formats
* clearer comparison across repeated task categories
* stronger runner-native automation where supported
* richer repo-level reporting built only from real execution history
* additional visible-session integration support across runners

Not part of the current product contract:

* hidden cross-session model state
* autonomous repo repair
* guaranteed optimization claims

---

## Read next

* [Usage](docs/USAGE.md)
* [Technical overview](docs/TECHNICAL_OVERVIEW.md)
* [Failure memory](docs/FAILURE_MEMORY.md)
* [Area memory](docs/AREA_MEMORY.md)
* [Work state](docs/WORK_STATE.md)
* [Safety](docs/SAFETY.md)
* [Execution summary](docs/EXECUTION_SUMMARY.md)
* [Demo](docs/DEMO.md)
* [Upgrade](docs/UPGRADE.md)
* [Limitations](docs/LIMITATIONS.md)

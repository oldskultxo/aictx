# AICTX

**Repo-local continuity runtime for coding agents.**

AICTX lives inside your repository so each new coding-agent session can start from the operational state left by previous work: active task state, next action, known failures, decisions, execution evidence, structural repo hints, and branch-safe Work State.

Install it once, initialize the repo, then keep using your coding agent normally.

AICTX is **Codex-first**, **Claude-aware**, and **generic-agent compatible**.

Current documented implementation: `5.0.0`

---

## Why this exists

Coding agents are powerful, but most sessions still start cold.

They rediscover repository structure, repeat failed paths, lose track of what was already verified, and depend on chat history for unfinished work.

AICTX gives them a repo-local continuity layer.

---

## What changes with AICTX

Without AICTX:

- the next session starts from a prompt and a fresh repo scan;
- failed approaches are easy to repeat;
- unfinished task state lives in chat history;
- the next action is easy to lose;
- branch switches can resume the wrong context.

With AICTX:

- the next session can load one compiled continuity capsule with `aictx resume`;
- active Work State preserves goal, hypothesis, files, next action, risks, and verified/unverified work;
- Failure Memory warns about known patterns;
- RepoMap can provide structural entry points so agents know where to look first;
- summaries preserve what changed and what can be reused;
- branch-safe loading avoids resuming active work on the wrong branch.

---

## Core capabilities

| Capability | What it does | Why it matters |
|---|---|---|
| **Work State** | Preserves the active task, hypothesis, next action, files, risks, and verification state | The next session knows what was in progress |
| **Failure Memory** | Stores observed command/test/build/type/lint failures as structured patterns | Agents can avoid repeating known mistakes |
| **RepoMap** | Optional Tree-sitter structural map of files and symbols | Agents get better “where should I look first?” context |
| **Strategy Memory** | Reuses successful prior execution patterns | Known-good approaches can be suggested again |
| **Handoff / Decisions** | Keeps operational summaries and explicit project decisions | Architecture and intent survive session boundaries |
| **Execution Summary** | Captures what happened at finalize time | The next session starts from factual continuity |
| **Resume capsule** | Compiles Work State, handoff, failures, decisions, strategies, and RepoMap into one agent brief | Agents do not need to discover AICTX internals at startup |

```text
Work State = what is currently in progress.
Failure Memory = what failed before.
RepoMap = where useful code likely lives.
Strategy Memory = what worked before.
Execution Summary = what changed in the last run.
Resume capsule = the one operational brief the agent consumes.
```

---

## Normal workflow

AICTX is designed to be **agent-driven after setup**.

From inside the repository, the normal setup is:

```bash
pip install aictx
aictx install
aictx init
aictx --version
```

`aictx --version` prints the installed CLI version so you can verify which AICTX release is active.

`aictx init --repo .` is the explicit form and is useful in scripts, CI, documentation, or when running from outside the target repository. When you are already inside the repo, `aictx init` is the simplest path.

After that, keep using your coding agent.

The generated repo instructions and hooks guide supported agents to call AICTX automatically. At normal task startup, supported agents should use one agent-facing continuity command:

```bash
aictx resume --repo . --request "<current user request>"
```

The user should not have to run AICTX command after command during normal work.

---

## What the agent calls

In normal supported workflows, AICTX is runtime plumbing for the agent.

At normal task startup, the agent-facing continuity query is:

```bash
aictx resume --repo . --request "<current user request>"
```

`resume` compiles Work State, handoffs, the latest execution summary, Strategy Memory, Failure Memory, Decisions, RepoMap, preferences, and relevant warnings into one compact operational capsule. It writes trace artifacts:

```text
.aictx/continuity/resume_capsule.md
.aictx/continuity/resume_capsule.json
```

Those capsule files are generated/local runtime artifacts, not durable portable continuity.

The runtime lifecycle still remains:

```text
prepare/startup context -> resume capsule -> work -> finalize -> final AICTX summary/persistence
```

`resume` does not replace `prepare_execution`, `finalize_execution`, the startup banner, the final AICTX summary, or persistence.

For normal agent startup, the startup banner data source is `resume.startup_banner_text` or `resume.startup_banner_render_payload`. In wrapped execution flows, it remains `prepare_execution().startup_banner_text`.

The final AICTX summary data source remains `finalize_execution().agent_summary_text`.

For wrapped execution, integrations may use:

```bash
aictx internal run-execution --repo . --request "..." -- ...
```

For diagnostics, demos, and power-user inspection, advanced surfaces remain callable:

```bash
aictx advanced
aictx next --json
aictx map query "..."
aictx task status --json
aictx report real-usage
```

Manual commands remain available for debugging, demos, power users, and integrations, but they are not the normal agent startup contract. The product experience is:

```text
install -> init -> use your coding agent
```

`internal boot` is a runtime/bootstrap diagnostic surface. The compact user-visible startup continuity banner is surfaced through prepare/startup continuity as `startup_banner_text`.

See [Installation](docs/INSTALLATION.md).

## Git-portable continuity

AICTX continuity can be made git-portable.

When enabled during `aictx init`, AICTX writes a selective `.gitignore` policy so a safe subset of canonical `.aictx/` artifacts can be committed with the repo. Another machine can clone/pull, run `aictx init`, and continue with the same repo-local continuity.

Git is the transport. AICTX does not require cloud sync.

See [Portability](docs/PORTABILITY.md).

---

## RepoMap has real weight

RepoMap is optional, but important.

Work State tells the agent **what** it was trying to do.  
RepoMap helps the agent know **where** to continue.

When installed with `aictx[repomap]`, AICTX can maintain a lightweight Tree-sitter-based structural index and expose file/symbol hints through:

```bash
aictx map status
aictx map refresh
aictx map query "startup banner"
```

AICTX works without RepoMap. With RepoMap enabled, the “cold repo discovery” part of agent sessions has a stronger structural starting point.

See [RepoMap](docs/REPOMAP.md).

---

## Supported agent model

AICTX is runner-aware, not runner-locked.

### Codex-first

Primary target:

- `AGENTS.md` repo instructions;
- optional global Codex install with `aictx install --install-codex-global`;
- CLI/runtime JSON contract;
- startup and summary guidance.

### Claude-aware

Supported through:

- `CLAUDE.md`;
- `.claude/settings.json`;
- `.claude/hooks/aictx_*.py`.

### Generic fallback

Any coding agent can use AICTX if it can read repo instructions, call CLI commands, and consume JSON/Markdown output.

---

## What you see

### Startup continuity

AICTX startup has two complementary surfaces:

- a compact startup banner from the prepare/startup lifecycle;
- a richer `aictx resume` capsule for the operational brief.

The banner is not the full handoff and does not replace `resume`.

AICTX produces a compact canonical startup banner in English. Supported agents may localize labels and connective wording to the current user language, but must preserve facts, file paths, commands, flags, test names, package names, and code identifiers.

Canonical runtime example:

```text
codex@aictx · session #40 · awake

Resuming: branch-safe Work State finalize behavior.
Last progress: finalize behavior aligned with tests.
Entry point: tests/test_work_state_runtime.py
Active task: Improve public docs. Next: update installation guide.
```

Optional agent-rendered localized example:

```text
codex@aictx · sesión #40 · despierto

Retomando: branch-safe Work State finalize behavior.
Último avance: finalize behavior aligned with tests.
Punto de entrada: tests/test_work_state_runtime.py
Tarea activa: Improve public docs. Siguiente: update installation guide.
```

Semantics:

- `Next:` means real pending work, for example `next_steps`, `open_items`, `blocked` items, or an active Work State `next_action`.
- `Entry point:` means a technical resume location from `recommended_starting_points` when there is no real pending work.

### Final summary

After execution, AICTX returns a compact factual summary for the agent’s final response.

Example shape:

```text
AICTX summary

Context: reused previous strategy + loaded handoff/decisions/preferences.
Map: RepoMap quick ok.
Saved: updated handoff.
Entry point: src/aictx/continuity.py, src/aictx/middleware.py.
Details: [last_execution_summary.md](.aictx/continuity/last_execution_summary.md)
```

---

## Branch-safe Work State

AICTX stores minimal git context with Work State:

- branch;
- HEAD commit;
- dirty flag;
- changed files;
- capture timestamp.

Loading rules:

- same branch -> load;
- different branch + saved commit is ancestor of current `HEAD` -> load with warning;
- different branch + saved commit is not ancestor -> skip;
- dirty saved state + different branch -> skip;
- old Work State or non-git repo -> load conservatively.

This is safety, not branch-aware task management.

---

## Artifact contract

The stable repo-local continuity artifact contract in `5.0.0` is:

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

Optional or latest-run artifacts may also appear:

```text
.aictx/continuity/handoffs.jsonl
.aictx/continuity/last_execution_summary.md
.aictx/continuity/resume_capsule.md
.aictx/continuity/resume_capsule.json
.aictx/area_memory/areas.json
.aictx/repo_map/config.json
.aictx/repo_map/manifest.json
.aictx/repo_map/index.json
.aictx/repo_map/status.json
```

---

## Who should use AICTX?

AICTX is for developers who repeatedly use coding agents in the same repository and want continuity without hidden cloud memory.

It is especially useful if you want agents to preserve:

- active task state;
- prior failures;
- verified and unverified work;
- relevant files and commands;
- repo structure hints;
- decisions and handoffs;
- next actions.

AICTX is not:

- a hosted agent platform;
- a dashboard or task manager;
- a vector database;
- hidden cloud memory;
- an autonomous repo repair system;
- a guarantee of productivity or token savings.

---

## Documentation

Start here:

- [Installation](docs/INSTALLATION.md)
- [Quickstart](docs/QUICKSTART.md)
- [Technical overview](docs/TECHNICAL_OVERVIEW.md)

Core concepts:

- [Work State](docs/WORK_STATE.md)
- [RepoMap](docs/REPOMAP.md)
- [Failure Memory](docs/FAILURE_MEMORY.md)
- [Strategy Memory](docs/STRATEGY_MEMORY.md)
- [Handoffs and Decisions](docs/HANDOFFS.md)
- [Execution Summary](docs/EXECUTION_SUMMARY.md)

Operations and trust:

- [Usage](docs/USAGE.md)
- [Cleanup](docs/CLEANUP.md)
- [Safety](docs/SAFETY.md)
- [Limitations](docs/LIMITATIONS.md)
- [Upgrade](docs/UPGRADE.md)
- [Demo](docs/DEMO.md)
- [Release checklist](docs/RELEASE_CHECKLIST.md)

---

## Current limits

AICTX improves continuity only when agents or integrations cooperate with the runtime contract. File access, commands, tests, and failures are strongest when passed explicitly or captured through wrapped execution.

AICTX does not claim measured productivity gains, guaranteed speedups, or automatic correctness.

It makes continuity visible, inspectable, and reusable.

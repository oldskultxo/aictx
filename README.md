# AICTX

[![PyPI](https://img.shields.io/pypi/v/aictx.svg)](https://pypi.org/project/aictx/)
[![Website](https://img.shields.io/badge/website-aictx.org-94b41e)](https://aictx.org)
[![Python](https://img.shields.io/pypi/pyversions/aictx.svg)](https://pypi.org/project/aictx/)
[![CI](https://github.com/oldskultxo/aictx/actions/workflows/ci.yml/badge.svg)](https://github.com/oldskultxo/aictx/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![PyPI Downloads](https://static.pepy.tech/personalized-badge/aictx?period=total&units=INTERNATIONAL_SYSTEM&left_color=GREY&right_color=BLUE&left_text=downloads)](https://pepy.tech/projects/aictx)

**Repo-local continuity for coding agents.**

**Official website:** https://aictx.org  
**Official repository:** https://github.com/oldskultxo/aictx  
**Official PyPI package:** https://pypi.org/project/aictx/  
**Official CLI:** `aictx`

AICTX helps a new coding-agent session start from the useful state left by the previous one: active task state, next action, known failures, decisions, execution evidence, and optional structural repo hints.

It is a local CLI/runtime layer for `.aictx_*` integrations. It stores inspectable artifacts in the repository under `.aictx/` and exposes one agent-facing resume command plus one finalize command.

AICTX is **Codex-first**, **GitHub Copilot-aware**, **Claude-aware**, and **generic-agent compatible**.

Current documented implementation: `6.4.1`

![AICTX + Coding Agent Runtime Flow](https://raw.githubusercontent.com/oldskultxo/aictx/main/docs/images/aictx-runtime-flow.png)

```bash
pip install aictx
aictx install
aictx init
```

[Quickstart](docs/QUICKSTART.md) · [Installation](docs/INSTALLATION.md) · [Demo](docs/DEMO.md) · [Technical overview](docs/TECHNICAL_OVERVIEW.md) · [Official project](docs/OFFICIAL_PROJECT.md)

---

## The problem

Coding agents are powerful, but most sessions still start cold:

- they rediscover the same repository structure;
- they reopen broad docs before the relevant source or test;
- they repeat failed commands or stale assumptions;
- unfinished work depends on chat history instead of repo-local state.

AICTX makes that continuity repo-local, inspectable, and reusable.

## What AICTX actually does

AICTX gives supported agents a small runtime loop:

```text
resume useful context -> do the work -> finalize factual evidence -> help the next session
```

At startup, an agent can call:

```bash
aictx resume --repo . --task "<task goal>" --json
```

After work, it records what happened:

```bash
aictx finalize --repo . --status success|failure --summary "<what happened>" --json
```

The next session can then receive a compact continuity capsule built from repo-local facts: Work State, handoffs, decisions, known failures, prior strategies, execution summaries, and optional RepoMap hints.

It is not a generic token compressor, autonomous coding system, hosted agent platform, or correctness guarantee.

AICTX combines continuity memory with structural repo lookup: Work State tells the agent what was happening; optional RepoMap tells it where to look first.

---

## See it in 30 seconds

Without AICTX, the next agent session often starts cold:

```text
User: continue parser work
Agent: scans repo, opens README, searches files, rediscovers tests...
```

With AICTX, the agent can start from a fresh resume capsule:

```bash
aictx resume --repo . --task "continue parser work" --json
```

Example shape:

```text
Resuming: parser edge cases
Last progress: BLOCKED status added
Next: expand tests/test_parser.py
Known failure: pytest unavailable outside .venv
Suggested command: .venv/bin/python -m pytest -q
```

The exact fields depend on what previous sessions actually recorded. AICTX does not invent missing facts.

---

## When to use it

Use AICTX when you:

- run multiple coding-agent sessions in the same repository;
- want explicit handoff, next action, decision, and failure memory;
- want repo-local continuity artifacts instead of hidden cloud memory;
- want optional structural entry points from RepoMap without making RepoMap mandatory.

Skip it if you want a hosted agent platform, a general knowledge base, or automatic correctness guarantees.

---

## Demo result

In a two-session coding task, AICTX helped the second session resume from the intended work surface instead of rediscovering the repo.

| Session 2 metric | Without AICTX | With AICTX |
|---|---:|---:|
| Files explored | 10 | 5 |
| Files edited | 3 | 1 |
| Commands run | 15 | 8 |
| Exploration before first edit | 15 | 6 |
| Time to complete | 1'59'' | 1'12'' |
| First relevant file | `README.md` | `tests/test_parser.py` |

This is not a universal benchmark. It is an observable continuity demo.
See [Demo](docs/DEMO.md).

---

## Install

From inside the repository:

```bash
pip install aictx
aictx install
aictx init
aictx --version
```

After that, keep using your coding agent.

`aictx init` creates the repo-local instruction surfaces used by supported runners, including `AGENTS.md`, `CLAUDE.md`, `.claude/*`, and `.github/copilot-instructions.md`. The Copilot file is a standard repository file intended to stay versioned in git.

The generated repo instructions and hooks guide supported agents to call AICTX automatically. The normal user experience is:

```text
install -> init -> use your coding agent
```

See [Installation](docs/INSTALLATION.md) and [Quickstart](docs/QUICKSTART.md).

---

## Project identity

AICTX is the official project maintained by Santi Santamaria / oldskultxo, published at https://aictx.org, and distributed through the `aictx` PyPI package.

It is not affiliated with similarly named npm packages, domains, or GitHub organizations.

For the canonical website / repository / package identity statement, see [Official project](docs/OFFICIAL_PROJECT.md).

---

## How it works

At normal task startup, supported agents use one continuity query:

```bash
aictx resume --repo . --task "<task goal>" --json
```

`--task` should contain only the work goal. `--task` is the only normal resume input in v6; legacy `--request` startup input has been removed.

After work, supported agents finalize factual evidence:

```bash
aictx finalize --repo . --status success|failure --summary "<what happened>" --json
```

In JSON mode, `resume` also includes bounded `loaded_context` metadata that explains why Work State, carryover, failures, handoffs, decisions, strategies, and RepoMap hints were selected. Each item includes role/relevance metadata such as `role`, `selection_reason`, `confidence`, `staleness`, and `related_paths`. It is additive inspection/debugging metadata, not proof of correctness and not hidden agent reasoning.

When RepoMap is enabled and indexed, `resume` can also include compact `structural_entry_points` and `structural_context`. RepoMap status separates provider, index, query, and refresh availability, so an existing index can remain queryable even if the provider is unavailable. Execution contracts may include `expected_first_files`, and finalize can record `structural_alignment`. RepoMap remains optional; AICTX continues to work without it.

The runtime loop is:

```text
resume capsule -> work -> finalize evidence -> next resume
```

Technical integrations can also use wrapped/internal execution surfaces. See [Technical overview](docs/TECHNICAL_OVERVIEW.md) and [Usage](docs/USAGE.md).

---

## Core capabilities

| Capability | What it does | Why it matters |
|---|---|---|
| **Work State** | Preserves active task, hypothesis, files, next action, risks, and verification state | The next session knows what was in progress |
| **Failure Memory** | Stores observed command/test/build/type/lint failures as structured patterns | Agents can avoid repeating known mistakes |
| **RepoMap** | Optional Tree-sitter structural map of files and symbols | Agents get compact structural entry points for “where should I look first?” |
| **Strategy Memory** | Reuses successful prior execution patterns | Known-good approaches can be suggested again |
| **Handoff / Decisions** | Keeps operational summaries and explicit project decisions | Architecture and intent survive session boundaries |
| **Execution Summary** | Captures what happened at finalize time | The next session starts from factual continuity |
| **Contract Compliance** | Audits first action, edit scope, validation, and structural alignment | Gaps can carry over into Work State instead of disappearing |
| **Doctor** | Read-only repo/runtime diagnostic with `aictx doctor --repo . --json`; add `--release-readiness` for strict aictx release-gate checks | Support uses a general repo diagnostic while releases keep stricter checks |
| **Resume capsule** | Compiles continuity into one agent brief | Agents do not need to discover AICTX internals at startup |

---

## How AICTX handles stale context

AICTX does not inject one permanent memory dump into every session.

Each task gets a fresh resume capsule built from repo-local artifacts: Work State, latest execution summary, decisions, known failures, strategy hints, and optional RepoMap data.

Old context is treated as context, not truth:

- Work State is branch-safe.
- Failures and strategies are observed evidence, not absolute instructions.
- Resume capsules are regenerated per task.
- Dedupe and staleness metadata help keep continuity bounded.
- Missing or unsafe context is skipped, warned about, or marked `not_evaluated` rather than invented.

See [Limitations](docs/LIMITATIONS.md) and [Technical overview](docs/TECHNICAL_OVERVIEW.md).

---

## Supported agents

AICTX is runner-aware, not runner-locked.

- **Codex-first:** `AGENTS.md`, optional global Codex setup, CLI/runtime JSON contract.
- **Claude-aware:** `CLAUDE.md`, `.claude/settings.json`, `.claude/hooks/aictx_*.py`.
- **GitHub Copilot:** repo-wide `.github/copilot-instructions.md` custom instructions created by `aictx init`.
- **Generic fallback:** any agent that can read repo instructions, run CLI commands, and consume JSON/Markdown.

---

## What AICTX is not

AICTX is not:

- a hosted agent platform;
- a dashboard or task manager;
- a vector database;
- hidden cloud memory;
- an autonomous repo repair system;
- a sandbox or enforcement layer;
- a guarantee of productivity, token savings, speedups, or correctness.

---

## Artifact contract

The stable repo-local continuity artifact contract in `6.4.1` is:

```text
.aictx/continuity/session.json
.aictx/continuity/handoff.json
.aictx/continuity/handoffs.jsonl
.aictx/continuity/decisions.jsonl
.aictx/continuity/semantic_repo.json
.aictx/continuity/semantic_repo/*
.aictx/continuity/dedupe_report.json
.aictx/continuity/staleness.json
.aictx/continuity/continuity_metrics.json
.aictx/continuity/contracts/*
.aictx/strategy_memory/strategies.jsonl
.aictx/failure_memory/failure_patterns.jsonl
.aictx/metrics/execution_logs.jsonl
.aictx/metrics/execution_feedback.jsonl
.aictx/metrics/contract_compliance.jsonl
.aictx/tasks/active.json
.aictx/tasks/threads/*
.aictx/area_memory/areas.json
.aictx/area_memory/areas/*
.aictx/repo_map/config.json
```

Optional or latest-run artifacts may also appear:

```text
.aictx/continuity/last_execution_summary.md
.aictx/continuity/resume_capsule.md
.aictx/continuity/resume_capsule.json
.aictx/repo_map/manifest.json
.aictx/repo_map/index.json
.aictx/repo_map/status.json
```

When `aictx init --portable-continuity` is enabled, AICTX still uses Git as the only transport. The 6.4.1 team-safe profile exposes append-only/sharded continuity artifacts to Git, keeps conflict-prone snapshots local-only, can add `.gitattributes` merge hints for portable JSONL files, and redacts detected secret-like values before writing the portable subset. See [Git-portable continuity](docs/PORTABILITY.md).

For lifecycle details, startup banner semantics, branch-safe loading rules, internal runtime commands, and compliance auditing, see [Technical overview](docs/TECHNICAL_OVERVIEW.md).

---

## Documentation

Start here:

- [Installation](docs/INSTALLATION.md)
- [Quickstart](docs/QUICKSTART.md)
- [Demo](docs/DEMO.md)
- [Technical overview](docs/TECHNICAL_OVERVIEW.md)

Core concepts:

- [Work State](docs/WORK_STATE.md)
- [RepoMap](docs/REPOMAP.md)
- [Failure Memory](docs/FAILURE_MEMORY.md)
- [Strategy Memory](docs/STRATEGY_MEMORY.md)
- [Handoffs and Decisions](docs/HANDOFFS.md)
- [Execution Summary](docs/EXECUTION_SUMMARY.md)
- [Execution Contracts and Compliance](docs/EXECUTION_CONTRACTS.md)
- [Doctor diagnostics](docs/DOCTOR.md)

Operations and trust:

- [Usage](docs/USAGE.md)
- [Cleanup](docs/CLEANUP.md)
- [Safety](docs/SAFETY.md)
- [Limitations](docs/LIMITATIONS.md)
- [Upgrade](docs/UPGRADE.md)
- [Release checklist](docs/RELEASE_CHECKLIST.md)
- [Contributing](CONTRIBUTING.md)

---

## Current limits

AICTX improves continuity only when agents or integrations cooperate with the runtime contract. File access, commands, tests, and failures are strongest when passed explicitly or captured through wrapped execution.

AICTX does not claim measured productivity gains, guaranteed speedups, or automatic correctness.

It makes continuity visible, inspectable, and reusable.

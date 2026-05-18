# AICTX

[![PyPI](https://img.shields.io/pypi/v/aictx.svg)](https://pypi.org/project/aictx/)
[![Website](https://img.shields.io/badge/website-aictx.org-94b41e)](https://aictx.org)
[![Python](https://img.shields.io/pypi/pyversions/aictx.svg)](https://pypi.org/project/aictx/)
[![CI](https://github.com/oldskultxo/aictx/actions/workflows/ci.yml/badge.svg)](https://github.com/oldskultxo/aictx/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![PyPI Downloads](https://static.pepy.tech/personalized-badge/aictx?period=total&units=INTERNATIONAL_SYSTEM&left_color=GREY&right_color=BLUE&left_text=downloads)](https://pepy.tech/projects/aictx)

**Operational continuity for AI coding agents.**

AICTX helps Codex, Claude, GitHub Copilot and other coding agents continue work across sessions by preserving the last useful execution state: active work, next actions, decisions, failures, validation evidence and repo context.

The next agent does not start from zero. It resumes from what actually happened.

**Website:** https://aictx.org  
**PyPI package:** https://pypi.org/project/aictx/  
**CLI:** `aictx`

It is a repo-local CLI/runtime layer for agent continuity. It stores inspectable artifacts under `.aictx/` and exposes one agent-facing resume command plus one finalize command.

AICTX is **Codex-first**, **GitHub Copilot-aware**, **Claude-aware**, and **generic-agent compatible**.

![AICTX + Coding Agent Runtime Flow](https://raw.githubusercontent.com/oldskultxo/aictx/main/docs/images/aictx-runtime-flow.png)

[Quickstart](docs/QUICKSTART.md) · [Installation](docs/INSTALLATION.md) · [Continuity View](docs/CONTINUITY_VIEW.md) · [Demo](docs/DEMO.md) · [Technical overview](docs/TECHNICAL_OVERVIEW.md) · [Official project](docs/OFFICIAL_PROJECT.md)

---

## The problem

Coding agents are powerful, but most sessions still start cold:

- they rediscover the same repository structure;
- they reopen broad docs before the relevant source or test;
- they repeat failed commands or stale assumptions;
- unfinished work depends on chat history instead of repo-local state.

AICTX makes that continuity repo-local, inspectable, and reusable.

## Install

Install AICTX, then initialize the repository:

```bash
pip install aictx
aictx install
aictx init
aictx --version
```

After that, keep using your coding agent.

The generated repo instructions and hooks guide supported agents to call AICTX automatically. The normal user experience is:

```text
install -> init -> use your coding agent
```

See [Installation](docs/INSTALLATION.md) and [Quickstart](docs/QUICKSTART.md).

---

## The operational continuity loop

```text
resume useful context -> do the work -> finalize evidence -> next session continues
```

AICTX stores continuity locally under `.aictx/`, so it is inspectable, reviewable and not dependent on hidden chat history.

## What changes?

### Without operational continuity

```text
A new agent session starts cold.
It scans README, docs, Makefile and source files.
It rediscovers decisions.
It may repeat failed commands.
It asks for context that already existed.
```

### With AICTX

```text
The agent runs one resume command.
It sees active work, next action, known failures and validation path.
After work, it finalizes factual evidence for the next session.
```

AICTX turns disconnected agent sessions into a continuous operational workflow.

## Inspect the continuity

```bash
aictx view --repo .
```

AICTX can render the current operational state of a repository as local Markdown and Mermaid:

```text
.aictx/reports/continuity-view.md
.aictx/reports/continuity-map.mmd
```

Not hidden memory. Reviewable operational continuity.

![AICTX Continuity View example](https://aictx.org/images/continuity-view.png)

[Continuity View documentation](docs/CONTINUITY_VIEW.md) · [Image asset](https://raw.githubusercontent.com/oldskultxo/aictx/main/docs/images/continuity-view.png)

## What AICTX preserves

AICTX focuses on operational facts that help the next agent continue useful work:

- active Work State and next action;
- execution summaries and handoffs;
- explicit decisions;
- known failures and resolved failure patterns;
- strategy hints from successful prior work;
- execution contracts and contract-compliance signals;
- optional RepoMap structural entry points;
- optional Git-portable continuity for small teams.

## What AICTX is not

AICTX is not an autonomous coding agent, a cloud memory service, a vector database, a dashboard, a replacement for human review, or a guarantee of correctness, productivity gains or token savings.

It is a repo-local operational continuity layer used by cooperating coding agents.

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
| **Continuity View** | Generates `.aictx/reports/continuity-view.md` and `.aictx/reports/continuity-map.mmd` from repo-local continuity | Users and agents can inspect active Work State, handoffs, failures, contracts, summaries, RepoMap hints, and portability in one deterministic Markdown/Mermaid view |
| **Contract Compliance** | Audits first action, edit scope, validation, and structural alignment | Gaps can carry over into Work State instead of disappearing |
| **Doctor** | Read-only repo/runtime diagnostic with `aictx doctor --repo . --json`; add `--release-readiness` for strict aictx release-gate checks | Support uses a general repo diagnostic while releases keep stricter checks |
| **Resume capsule** | Compiles continuity into one agent brief | Agents do not need to discover AICTX internals at startup |

---

## Supported agents

AICTX is runner-aware, not runner-locked.

- **Codex-first:** `AGENTS.md`, optional global Codex setup, CLI/runtime JSON contract.
- **Claude-aware:** `CLAUDE.md`, `.claude/settings.json`, `.claude/hooks/aictx_*.py`.
- **GitHub Copilot:** best-effort instruction hardening through `.github/copilot-instructions.md`, `.github/instructions/aictx.instructions.md`, and optional prompt files created by `aictx init`.
- **Generic fallback:** any agent that can read repo instructions, run CLI commands, and consume JSON/Markdown.

---

## Documentation

Start here:

- [Installation](docs/INSTALLATION.md)
- [Quickstart](docs/QUICKSTART.md)
- [Demo](docs/DEMO.md)
- [Technical overview](docs/TECHNICAL_OVERVIEW.md)

Core concepts:

- [AI coding agent memory](docs/concepts/ai-coding-agent-memory.md)
- [Repo-local continuity](docs/concepts/repo-local-memory.md)
- [Operational continuity](docs/concepts/operational-memory.md)
- [Failure memory for coding agents](docs/concepts/failure-memory-for-coding-agents.md)
- [Work State](docs/WORK_STATE.md)
- [RepoMap](docs/REPOMAP.md)
- [Failure Memory](docs/FAILURE_MEMORY.md)
- [Strategy Memory](docs/STRATEGY_MEMORY.md)
- [Handoffs and Decisions](docs/HANDOFFS.md)
- [Execution Summary](docs/EXECUTION_SUMMARY.md)
- [Execution Contracts and Compliance](docs/EXECUTION_CONTRACTS.md)
- [Doctor diagnostics](docs/DOCTOR.md)

Use cases and comparisons:

- [Codex operational continuity](docs/use-cases/codex-memory.md)
- [Claude Code operational continuity](docs/use-cases/claude-code-memory.md)
- [GitHub Copilot operational continuity](docs/use-cases/github-copilot-memory.md)
- [AICTX vs AGENTS.md](docs/compare/aictx-vs-agents-md.md)
- [AICTX vs long context](docs/compare/aictx-vs-long-context.md)
- [AICTX vs vector databases](docs/compare/aictx-vs-vector-database.md)
- [AICTX vs chat history](docs/compare/aictx-vs-chat-history.md)

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

It makes operational continuity visible, inspectable, and reusable.

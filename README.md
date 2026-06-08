# AICTX

[![PyPI](https://img.shields.io/pypi/v/aictx.svg)](https://pypi.org/project/aictx/)
[![CI](https://github.com/oldskultxo/aictx/actions/workflows/ci.yml/badge.svg)](https://github.com/oldskultxo/aictx/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/pypi/pyversions/aictx.svg)](https://pypi.org/project/aictx/)
[![Website](https://img.shields.io/badge/website-aictx.org-94b41e)](https://aictx.org)

**Stop onboarding your coding agents from scratch every session.**

AICTX is a lightweight repo-local continuity runtime for Codex, Claude Code, GitHub Copilot, and other coding agents. It gives each new session the useful facts from the repository — what happened, what failed, what changed, what was decided, and what should happen next — without turning AICTX into an agent framework, task manager, vector database, or cloud memory product.

![AICTX stops onboarding coding agents like rookies every session](https://aictx.org/images/aictx-stop-onboarding-rookies.png)

```bash
pip install aictx
aictx install
aictx init
```

After that, keep working normally. Compatible agents run the lifecycle themselves:

```text
resume -> work -> finalize -> next session resumes
```

[Quickstart](docs/QUICK-START.md) · [What AICTX writes](docs/WHAT-AICTX-WRITES.md) · [Continuity View](docs/CONTINUITY_VIEW.md) · [Website](https://aictx.org)

---

## Why AICTX exists

Coding agents are strong, but new sessions still start cold:

- they rescan the same files and docs;
- they rediscover decisions already made;
- they repeat failed commands and stale assumptions;
- useful context gets trapped in one vendor's chat history.

AICTX turns that fragile chat-local memory into repo-local operational continuity. The next agent starts with a compact brief instead of guessing from scratch.

## The product loop

The user path is intentionally small:

```text
aictx install
aictx init
then let the coding agent work
```

The agent path is equally small:

```bash
aictx resume --repo . --task "fix the parser bug" --json
# agent edits, tests, debugs, and reviews normally
aictx finalize --repo . --status success --summary "Fixed parser recovery and ran focused parser tests" --json
```

A later session resumes from local repository state instead of hidden chat history.

```text
You: fix the parser bug
Agent: resumes repo-local continuity
Agent: works normally
Agent: finalizes factual evidence for the next session
```

## What the next agent gets

AICTX records operational facts that make the next session useful faster:

| Continuity | Why it helps |
|---|---|
| **Active work** | Current task, files, risks, and next action. |
| **Handoffs** | What the previous session actually left behind. |
| **Decisions** | Project facts the next agent should not re-litigate. |
| **Failures** | Known broken commands, errors, and resolved patterns. |
| **Validation evidence** | Commands, tests, files opened/edited, and final summary. |
| **Quality signals** | Fresh, stale, missing, obsolete, or unverified context warnings. |

Everything is local and inspectable. The default runtime writes under `.aictx/` and generated agent-instruction files; no account, daemon, dashboard, or cloud sync service is required.

## See it working

Generate an inspectable continuity report at any time:

```bash
aictx view --repo .
```

Default output:

```text
.aictx/reports/continuity-view.md
.aictx/reports/continuity-map.mmd
```

Check health and repair guidance:

```bash
aictx doctor --repo . --json
```

AICTX is not hidden memory. It is reviewable repo-local continuity with explicit quality signals.

## Why it feels different

- **Local-first:** continuity belongs to the repository, not a private chat thread.
- **Agent-neutral:** Codex can leave context that Claude Code, Copilot, or another compatible agent can resume.
- **Tiny default path:** install, init, then work; manual resume/finalize commands are mostly for inspection and unsupported runners.
- **Evidence-oriented:** AICTX records what was observed, validated, skipped, or left unfinished.
- **Honest by design:** stale context is marked stale; missing validation stays visible; AICTX never claims automatic correctness.

## Supported agents

AICTX is runner-aware, not runner-locked.

- **Codex:** `AGENTS.md`, optional global Codex setup, CLI/MCP lifecycle guidance.
- **Claude Code:** `CLAUDE.md`, Claude settings/hooks, CLI/MCP lifecycle guidance.
- **GitHub Copilot:** repository instructions and optional prompt files where supported.
- **Generic agents:** any runner that can read instructions and call CLI or MCP tools.

Compatible agents prefer AICTX MCP tools when available and fall back to the CLI:

```text
aictx_resume / aictx_finalize
# or
aictx resume --repo . --task "<goal>" --json
aictx finalize --repo . --status success|failure --summary "<what happened>" --json
```

## What AICTX is not

AICTX is not an autonomous coding agent, RAG system, vector database, task manager, dashboard, cloud memory service, replacement for tests/review, or guarantee of correctness, productivity gains, or token savings.

It is a lightweight continuity runtime that helps cooperating coding agents start from useful repository state.

## Documentation

Start here:

- [Quickstart](docs/QUICK-START.md)
- [Installation](docs/INSTALLATION.md)
- [Usage](docs/USAGE.md)
- [What AICTX writes](docs/WHAT-AICTX-WRITES.md)
- [Continuity View](docs/CONTINUITY_VIEW.md)
- [Doctor diagnostics](docs/DOCTOR.md)

Core concepts:

- [Technical overview](docs/TECHNICAL_OVERVIEW.md)
- [Work State](docs/WORK_STATE.md)
- [Handoffs and Decisions](docs/HANDOFFS.md)
- [Failure Memory](docs/FAILURE_MEMORY.md)
- [Execution Summary](docs/EXECUTION_SUMMARY.md)
- [Execution Contracts](docs/EXECUTION_CONTRACTS.md)

Advanced:

- [MCP](docs/MCP.md)
- [RepoMap](docs/REPOMAP.md)
- [Portability](docs/PORTABILITY.md)
- [Continuity Guard](docs/CONTINUITY_GUARD.md)
- [Steer Guard](docs/STEER_GUARD.md)
- [Cleanup](docs/CLEANUP.md)
- [Safety](docs/SAFETY.md)
- [Limitations](docs/LIMITATIONS.md)

Legacy/internal compatibility surfaces are intentionally kept out of the first-run path; see [Usage](docs/USAGE.md) for the split between supported advanced commands and compatibility-only commands.

For the full command reference, see [Usage](docs/USAGE.md).

## Project links

- Website: https://aictx.org
- PyPI: https://pypi.org/project/aictx/
- CLI: `aictx`
- Official identity: [docs/OFFICIAL_PROJECT.md](docs/OFFICIAL_PROJECT.md)

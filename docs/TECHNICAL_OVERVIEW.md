---
title: "AICTX Technical Overview"
description: "Technical overview of AICTX as a lightweight repo-local continuity runtime for coding agents."
---

# Technical overview

AICTX is a lightweight repo-local continuity runtime for coding agents.

It is not an agent framework, RAG system, vector database, dashboard, task manager, or cloud memory service. It stores bounded operational continuity in the repository so a later coding-agent session can start from useful facts instead of rebuilding context from scratch.

## Core lifecycle

User setup:

```text
aictx install -> aictx init
```

Agent runtime:

```text
resume -> work -> finalize -> later resume
```

Public commands:

```bash
aictx resume --repo . --task "<goal>" --json
aictx finalize --repo . --status success|failure --summary "<what happened>" --json
aictx doctor --repo . --json
aictx view --repo .
```

## Components

| Component | Role |
|---|---|
| Repo scaffold | Creates `.aictx/` and managed instruction/config files. |
| Runner integrations | Gives Codex, Claude Code, GitHub Copilot, and generic agents the same lifecycle instructions. |
| Resume capsule | Compiles Work State, handoffs, decisions, failures, quality signals, optional RepoMap hints, and execution contract into an agent brief. |
| Finalize | Persists observed files, commands, tests, errors, status, summary, handoff, and quality evidence. |
| Work State | Tracks suspended or active work when there is useful next-action state. |
| Handoffs and Decisions | Preserve factual continuity across sessions. |
| Failure Memory | Stores observed failure patterns and known bad paths. |
| Execution Contracts | Provide advisory first action, edit scope, validation expectation, and finalization expectation. |
| Continuity Quality | Marks context fresh, stale, missing, obsolete, demoted, or unverified. |
| Continuity View | Renders deterministic Markdown/Mermaid reports. |
| Doctor | Gives read-only diagnostics and repair guidance. |
| RepoMap | Optional structural file/symbol hints. Not required for the core lifecycle. |
| MCP | Local stdio surface over the same runtime as the CLI. |

## Install vs init

`aictx install` prepares global/runtime setup such as workspace metadata, MCP runtime metadata, optional global Codex files, and optional RepoMap support.

`aictx init` prepares one repository. It may write `.aictx/`, generated agent instructions, repo-local MCP config, `.gitignore` managed blocks, Claude/Copilot/Codex integration files, and optional RepoMap artifacts.

See [What AICTX writes](WHAT-AICTX-WRITES.md).

## Resume

At startup, the agent-facing continuity query is:

```bash
aictx resume --repo . --task "<task goal>" --json
```

`resume` may include:

- startup banner policy and text/payload;
- lifecycle warnings;
- loaded context metadata;
- active or carried Work State;
- handoff and decision summaries;
- known failures;
- optional structural entry points from RepoMap;
- continuity quality signals;
- execution contract and validation policy.

`resume` is the canonical agent-facing continuity query. It does not replace finalization or persistence.

## Finalize

After work, agents should close the loop:

```bash
aictx finalize --repo . --status success --summary "<what happened>" --json
```

Finalization records factual evidence and returns the compact AICTX summary that agents should append to the user-facing final response when available.

With `--include-view`, finalize can also generate Continuity View links.

## Public, advanced, and legacy surfaces

Main product surface:

```text
install, init, resume, finalize, doctor, view, clean
```

Advanced but valid surface:

```text
mcp, portability, map, guard, steer
```

Legacy/internal compatibility surfaces are intentionally not part of the first-run path. They can exist for old integrations or diagnostics, but docs and generated guidance should keep users focused on the lifecycle above.

## Agent integrations

All supported integrations should communicate the same model:

```text
install, init, then let the agent work
```

When MCP tools are visible, agents should prefer `aictx_resume` and `aictx_finalize`. If MCP is unavailable, use CLI fallback. Generated instructions should not make users learn legacy memory subsystems.

## Trust model

AICTX continuity is evidence, not truth.

- Stale or missing context stays visible as risk.
- RepoMap hints are structural hints, not semantic proof.
- Failure records are observed patterns, not future guarantees.
- Execution contracts are advisory/audit-only; they do not sandbox the agent.
- AICTX does not guarantee correctness, speedups, token savings, or complete agent compliance.

## Related docs

Start here:

- [Quickstart](QUICK-START.md)
- [Installation](INSTALLATION.md)
- [Usage](USAGE.md)
- [What AICTX writes](WHAT-AICTX-WRITES.md)

Core concepts:

- [Work State](WORK_STATE.md)
- [Handoffs and Decisions](HANDOFFS.md)
- [Failure Memory](FAILURE_MEMORY.md)
- [Execution Summary](EXECUTION_SUMMARY.md)
- [Execution Contracts](EXECUTION_CONTRACTS.md)
- [Continuity View](CONTINUITY_VIEW.md)
- [Doctor](DOCTOR.md)

Advanced:

- [MCP](MCP.md)
- [RepoMap](REPOMAP.md)
- [Portability](PORTABILITY.md)
- [Continuity Guard](CONTINUITY_GUARD.md)
- [Steer Guard](STEER_GUARD.md)

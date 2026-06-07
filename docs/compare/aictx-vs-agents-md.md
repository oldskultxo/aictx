---
title: "AICTX vs AGENTS.md"
description: "Compare AGENTS.md instructions with AICTX repo-local memory, runtime continuity artifacts, failure memory, and handoff workflows for coding agents."
---

# AICTX vs AGENTS.md

`AGENTS.md` tells agents how to behave in a repository. AICTX helps them remember what actually happened there. AICTX can generate and use instructions, but it is broader than an instruction file.

AICTX adds repo-local runtime continuity: Work State, handoffs, decisions, failure memory, execution summaries, and optional RepoMap hints.

## The difference

| Capability | AGENTS.md | AICTX |
| --- | --- | --- |
| Static repository instructions | Yes | Yes, through scaffolded instructions |
| Active task Work State | No | Yes |
| Failure memory | No | Yes |
| Handoff memory | Manual only | Yes |
| Resume/finalize lifecycle | No | Yes |
| Repo-local continuity artifacts | No | Yes |

## When AGENTS.md is enough

An instruction file may be enough when a project only needs stable rules: coding style, test commands, and repository conventions.

## When AICTX helps

AICTX is useful when sessions need operational memory: what was active, what failed, what was decided, and what the next agent should do.

Related docs:
- [Technical overview](/TECHNICAL_OVERVIEW.html)
- [Work State](/WORK_STATE.html)
- [Failure Memory](/FAILURE_MEMORY.html)
- [Official AICTX project identity](/OFFICIAL_PROJECT.html)

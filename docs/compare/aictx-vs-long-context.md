---
title: "AICTX vs Long Context"
description: "Compare long-context prompts with AICTX repo-local continuity, structured operational memory, failure memory, and handoffs for coding agents."
---

# AICTX vs Long Context

Long context can hold more text in one model interaction. AICTX solves a different problem: preserving the structured repo-local facts that a later coding-agent session should not have to rediscover.

AICTX and long context can work together. Long context helps within a session; AICTX stores operational memory for future sessions.

## The difference

| Capability | Long context | AICTX |
| --- | --- | --- |
| More text in one prompt | Yes | Not the goal |
| Repo-local continuity across sessions | Provider-dependent | Yes |
| Work State | Manual | Yes |
| Failure memory | Manual | Yes |
| Handoff memory | Manual | Yes |
| Inspectable local artifacts | No by default | Yes |

## Why continuity is different from context length

A larger context window does not automatically preserve decisions, known failures, next actions, or execution evidence in the repository. AICTX records those facts as local artifacts that later sessions can load.

Related docs:
- [AI coding agent memory](/concepts/ai-coding-agent-memory.html)
- [Repo-local memory](/concepts/repo-local-memory.html)
- [Technical overview](/TECHNICAL_OVERVIEW.html)
- [Official AICTX project identity](/OFFICIAL_PROJECT.html)

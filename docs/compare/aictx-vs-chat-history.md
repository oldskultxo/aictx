---
title: "AICTX vs Chat History"
description: "Compare provider chat history with AICTX repo-local memory, handoffs, failure memory, and coding-agent continuity artifacts."
---

# AICTX vs Chat History

Chat history is useful, but it is usually tied to a provider, tool, account, or session. AICTX stores repo-local memory that belongs to the project.

AICTX does not replace conversation history. It records operational continuity in inspectable repository artifacts.

## The difference

| Capability | Chat history | AICTX |
| --- | --- | --- |
| Conversational transcript | Yes | No |
| Repo-local Work State | No by default | Yes |
| Failure memory | Manual | Yes |
| Handoff memory | Manual | Yes |
| Portable through Git | No by default | Optional |
| Inspectable project artifacts | No by default | Yes |

## Why repo-local continuity matters

A future coding-agent session may not have the same chat history. AICTX records the operational facts needed to continue work: what was active, what failed, what was decided, and what should happen next.

Related docs:
- [Handoffs](/HANDOFFS.html)
- [Work State](/WORK_STATE.html)
- [Repo-local memory](/concepts/repo-local-memory.html)
- [Official AICTX project identity](/OFFICIAL_PROJECT.html)

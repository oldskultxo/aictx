---
title: "Failure Memory for Coding Agents"
description: "Understand failure memory for coding agents and how AICTX records observed command, test, build, and lint failures as repo-local continuity."
---

# Failure Memory for Coding Agents

Failure memory is repo-local memory of observed failures and their context. It helps future coding-agent sessions avoid blindly repeating known failed paths.

AICTX failure memory is based on observed command, test, build, lint, typecheck, or compilation failures when those facts are captured by the runtime.

## What failure memory can include

- failed command or test context;
- error summaries;
- related files or areas;
- resolution links when a later session fixes the issue;
- recurrence signals for similar failures.

## What failure memory does not guarantee

Failure memory does not guarantee that future agents will avoid every repeated mistake. It provides inspectable continuity signals that a cooperating agent can use.

Related docs:
- [Failure Memory](/FAILURE_MEMORY.html)
- [Operational memory](/concepts/operational-memory.html)
- [Technical overview](/TECHNICAL_OVERVIEW.html)
- [Official AICTX project identity](/OFFICIAL_PROJECT.html)

---
title: "Operational Memory for Coding Agents"
description: "Understand operational memory for coding agents: task state, command outcomes, failures, decisions, handoffs, and next actions."
---

# Operational Memory for Coding Agents

Operational memory is memory about work: what happened, what failed, what was decided, and what should happen next. It is the practical layer that prevents every new agent session from rebuilding context from scratch.

AICTX focuses on operational memory because coding agents often need execution context more than a broad transcript.

## Examples of operational memory

- active task and next action;
- command, test, build, and lint failures;
- decision records;
- handoff summaries;
- execution summaries;
- relevant repository areas.

## How AICTX records it

AICTX uses a resume/finalize lifecycle. A coding agent resumes from useful context before work and finalizes factual evidence after work.

Related docs:
- [Technical overview](/TECHNICAL_OVERVIEW.html)
- [Execution Summary](/EXECUTION_SUMMARY.html)
- [Failure Memory](/FAILURE_MEMORY.html)
- [Official AICTX project identity](/OFFICIAL_PROJECT.html)

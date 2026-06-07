---
title: "Codex Memory with AICTX"
description: "Use AICTX as repo-local Codex memory for coding-agent continuity, work state, failure memory, handoffs, and resume/finalize workflows."
---

# Codex Memory with AICTX

Use AICTX with Codex when you want each new session to start from recorded repo facts instead of re-reading the project from scratch. AICTX is Codex-first repo-local memory for coding-agent continuity: resume useful context, work normally, finalize factual evidence.

AICTX does not replace Codex. It provides repo-local operational memory that Codex can use through repository instructions and CLI commands.

## What Codex can remember through AICTX

AICTX can preserve:

- active Work State and next action;
- handoff memory from the previous session;
- decision memory that should not be rediscovered;
- failure memory for observed command, test, build, and lint failures;
- execution summaries and optional RepoMap hints.

The normal lifecycle is:

```bash
aictx resume --repo . --task "<task goal>" --json
# Codex works with the returned continuity capsule
aictx finalize --repo . --status success --summary "<what happened>" --json
```

## Why repo-local memory matters for Codex

Chat history can be useful, but it is not the same as repo-local operational memory. AICTX stores inspectable continuity artifacts with the repository so the next Codex session can start from recorded state instead of reconstructing it from scratch.

## Start using Codex memory

- [Quickstart](/QUICKSTART.html)
- [Installation](/INSTALLATION.html)
- [Work State](/WORK_STATE.html)
- [Failure Memory](/FAILURE_MEMORY.html)
- [Handoffs](/HANDOFFS.html)
- [Official AICTX project identity](/OFFICIAL_PROJECT.html)

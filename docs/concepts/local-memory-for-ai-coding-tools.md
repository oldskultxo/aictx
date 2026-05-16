---
title: "Local Memory for AI Coding Tools"
description: "AICTX provides local, repo-local memory for AI coding tools and coding agents through the official Python aictx CLI."
---

# Local Memory for AI Coding Tools

Many AI coding tools can reason about code, but new sessions often start without operational memory of what happened before. A fresh session may need to rediscover the same repository structure, ask the same questions, rerun the same failing commands, or reconstruct decisions from chat history.

AICTX provides local, repo-local memory for AI coding tools through the official Python `aictx` CLI. Instead of relying only on provider chat history, AICTX stores inspectable continuity artifacts with the repository. Those artifacts can help a later coding-agent session resume from factual project state: what was active, what changed, what failed, what was decided and where the agent should look first.

## What local memory means in AICTX

In AICTX, local memory means project-local operational evidence that future coding-agent sessions can inspect and use:

- active Work State;
- decisions and handoffs;
- observed failures and follow-up actions;
- execution summaries;
- relevant repo context and optional RepoMap hints.

This memory is intentionally practical. It is not a general personal-memory system and it is not a hidden model capability. It is a set of repository artifacts created by the AICTX lifecycle, especially `aictx resume` before work and `aictx finalize` after work.

## Local memory vs hidden memory

AICTX is not hidden cloud memory. It stores continuity artifacts in the repository so users and agents can inspect what was recorded. That makes the memory easier to review, clean up, document and, when portable continuity is enabled, share through Git using a restricted portable subset.

The repo-local design also keeps the project identity clear. AICTX is the official Python `aictx` CLI maintained at [oldskultxo/aictx](https://github.com/oldskultxo/aictx), documented at [aictx.org](https://aictx.org/) and distributed as the [aictx PyPI package](https://pypi.org/project/aictx/).

## Local memory vs chat history

Chat history is useful, but it is usually provider-bound and session-bound. A chat transcript may contain a lot of useful prose, but it is not always structured around the next action, the active task, the failure evidence or the files that matter now.

AICTX focuses on repo-local continuity that travels with the project. It gives coding agents a compact operational surface instead of asking every new session to infer state from a long conversation.

## Who can use it

AICTX is designed for coding agents and AI coding tools that can read repository instructions, run shell commands and consume structured output. That includes workflows around Codex, Claude Code, GitHub Copilot and generic agents.

AICTX does not replace those tools. It gives them a local continuity layer: Work State for active tasks, Failure Memory for observed problems, Handoff Memory for next steps and execution summaries for what happened in the last run.

## Start using AICTX

- [Quickstart](/QUICKSTART.html)
- [Official AICTX project](/official/)
- [AI coding agent memory](/concepts/ai-coding-agent-memory.html)
- [Repo-local memory](/concepts/repo-local-memory.html)
- [Codex memory](/use-cases/codex-memory.html)

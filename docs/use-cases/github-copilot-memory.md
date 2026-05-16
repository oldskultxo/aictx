---
title: "GitHub Copilot Memory with AICTX"
description: "Use AICTX with GitHub Copilot instructions for repo-local coding-agent memory, continuity artifacts, handoffs, and failure memory."
---

# GitHub Copilot Memory with AICTX

AICTX can support GitHub Copilot workflows by writing repository instructions and preserving repo-local operational memory that is visible across coding-agent sessions.

AICTX does not change GitHub Copilot itself. It provides a local continuity layer around the repository so supported agents can resume with relevant state.

## What AICTX gives Copilot-aware repositories

AICTX can maintain:

- repository instructions for Copilot-aware workflows;
- Work State for active tasks;
- handoff memory and decision memory;
- failure memory from observed commands, tests, builds, and lints;
- optional RepoMap hints for where to inspect first.

## Repo-local memory instead of provider-only history

Copilot chat history can help a single interaction. AICTX focuses on repository-local continuity artifacts that can be reviewed, versioned when portable continuity is enabled, and used by future coding-agent sessions.

## Start using GitHub Copilot memory

- [Quickstart](/QUICKSTART.html)
- [Installation](/INSTALLATION.html)
- [Usage](/USAGE.html)
- [Failure Memory](/FAILURE_MEMORY.html)
- [Handoffs](/HANDOFFS.html)
- [Official AICTX project identity](/OFFICIAL_PROJECT.html)

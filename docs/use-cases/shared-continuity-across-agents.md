---
title: "Shared Continuity Across Coding Agents"
description: "Use AICTX as repo-local shared continuity so Codex, Claude Code, GitHub Copilot, and generic coding agents can hand off through the same project state."
---

# Shared Continuity Across Coding Agents

AICTX can act as shared repo-local memory for multiple coding agents. Instead of continuity living inside one provider's chat history, AICTX stores operational facts in the repository so another agent can resume from the same state.

This matters when you use different agents for different jobs:

- Codex for longer implementation sessions;
- Claude Code for review, refactoring, or reasoning-heavy work;
- GitHub Copilot inside the IDE;
- generic agents or scripts that can read repo instructions and run CLI commands.

## The cross-agent handoff loop

```text
Codex works on the repo
  -> aictx finalize stores what happened
  -> .aictx/ keeps Work State, decisions, failures, summaries and next actions
  -> Claude Code, Copilot or another agent runs aictx resume
  -> the next agent starts from factual repo continuity
```

The important point is that the memory belongs to the repository, not to a single chat session.

## What gets shared

AICTX can share practical operational continuity:

- active Work State and next action;
- handoffs and execution summaries;
- project decisions;
- known failures and resolved failure patterns;
- validation evidence and expected checks;
- optional RepoMap structural hints;
- Continuity View and Continuity Quality signals.

This does not make agents identical. Each tool still has its own strengths and runtime. AICTX gives them a common continuity surface.

## Why this is different from chat history

Provider chat history is useful, but it is usually bound to one tool, one account, or one session. If you switch from Codex to Claude Code or from a chat agent to Copilot in the IDE, the next tool may not know what was already tried.

AICTX records the operational evidence in `.aictx/`. Compatible agents can use `aictx resume --repo . --task "<goal>" --json`, MCP tools, or generated repo instructions to load that evidence.

## Example

```bash
# Agent A finishes work
aictx finalize --repo . --status success --summary "updated parser; pytest tests/test_parser.py passed" --json

# Later, Agent B starts from the same repo-local continuity
aictx resume --repo . --task "continue parser cleanup" --json
```

Agent B can see the previous summary, relevant files, validation path, failures, decisions, and any active Work State that remains.

## Start using shared continuity

- [Quickstart](/QUICKSTART.html)
- [Installation](/INSTALLATION.html)
- [Codex memory](/use-cases/codex-memory.html)
- [Claude Code memory](/use-cases/claude-code-memory.html)
- [GitHub Copilot memory](/use-cases/github-copilot-memory.html)
- [Continuity View](/CONTINUITY_VIEW.html)

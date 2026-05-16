---
title: "GitHub Copilot Memory with AICTX"
description: "Use AICTX with GitHub Copilot instructions for repo-local coding-agent memory, continuity artifacts, handoffs, and failure memory."
---

# GitHub Copilot Memory with AICTX

AICTX can support GitHub Copilot workflows by writing repository instructions, path-specific instruction files and optional prompt files while preserving repo-local operational memory that is visible across coding-agent sessions.

AICTX does not change GitHub Copilot itself and cannot force Copilot to run commands. It provides a local continuity layer around the repository so supported Copilot surfaces can use instructions to resume with relevant state when command execution is available.

## What AICTX gives Copilot-aware repositories

AICTX can maintain:

- repository-wide instructions in `.github/copilot-instructions.md`;
- path-specific instructions in `.github/instructions/aictx.instructions.md`;
- optional prompt files in `.github/prompts/`;
- Work State for active tasks;
- handoff memory and decision memory;
- failure memory from observed commands, tests, builds, and lints;
- optional RepoMap hints for where to inspect first.

## Repo-local memory instead of provider-only history

Copilot chat history can help a single interaction. AICTX focuses on repository-local continuity artifacts that can be reviewed, versioned when portable continuity is enabled, and used by future coding-agent sessions. In Copilot Chat, expand response References to check whether `.github/copilot-instructions.md` was included.


## Best-effort instruction model

GitHub Copilot custom instructions are not hooks or wrappers. They increase the chance that Copilot follows the AICTX lifecycle, but behavior can vary by Copilot surface, user settings, organization instructions and available tool execution.

For non-trivial repository work, AICTX asks Copilot to run:

```bash
aictx resume --repo . --task "<task goal>" --agent-id copilot --adapter-id copilot-vscode --json
aictx finalize --repo . --status success|failure --summary "<what happened>" --agent-id copilot --adapter-id copilot-vscode --json
```

If terminal execution is unavailable, Copilot should say that the AICTX lifecycle could not be executed.

## Start using GitHub Copilot memory

- [Quickstart](/QUICKSTART.html)
- [Installation](/INSTALLATION.html)
- [Usage](/USAGE.html)
- [Failure Memory](/FAILURE_MEMORY.html)
- [Handoffs](/HANDOFFS.html)
- [Official AICTX project identity](/OFFICIAL_PROJECT.html)

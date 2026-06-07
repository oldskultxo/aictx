---
title: "AICTX Quickstart for Operational Continuity"
description: "Start using AICTX to preserve operational continuity across AI coding-agent sessions with the official aictx CLI."
---

# Quickstart

This walkthrough gets a repository from zero to its first visible continuity loop: install, initialize, resume, finalize, inspect.

AICTX is built around one loop:

```text
resume before work -> work normally -> finalize evidence -> next session continues
```

## 1. Install and Initialize

```bash
pip install aictx
aictx install
aictx init
```

That is the normal user path.

```text
You install and initialize AICTX.
Supported agents are instructed to resume before work and finalize after work.
Everything is stored locally under `.aictx/`.
```

If `~/.codex/` already exists, `aictx install` detects Codex and installs/updates AICTX-managed global Codex integration by default. In interactive mode it asks for confirmation; with `--yes` it applies the detected Codex setup automatically.

Optional check:

```bash
aictx --version
aictx doctor --repo . --json
```

A fresh repo may have little continuity. That is expected. AICTX becomes more useful after work has been finalized and Work State, failures, decisions, or handoffs exist.

### MCP support

By default, `aictx install` prepares AICTX MCP runtime metadata and `aictx init` writes repo-local MCP config for compatible clients.

Compatible agents can launch the local stdio server with:

```bash
aictx mcp-server --repo . --profile full
```

Inspect MCP setup with:

```bash
aictx mcp status --repo .
```

Opt out with:

```bash
aictx install --no-mcp
aictx init --no-mcp
```

Agents should prefer MCP tools such as `aictx_resume`, `aictx_finalize`, and `aictx_view` when available, and fall back to CLI commands otherwise.

### Interactive install
Installation prepares AICTX MCP support by default and will only ask you about enabling recommended RepoMap support using Tree-sitter.

RepoMap uses Tree-sitter to build a compact structural map of files and symbols. It helps agents choose better starting points without reading the whole repo.

### Runtime behavior

`aictx init` no longer asks you to choose a communication mode. AICTX prepares repo-local continuity and runner instructions; after that, the coding agent should use `resume -> work -> finalize` while normal user/agent communication remains under the current user and runner controls. Older repos that still contain legacy communication-mode preferences remain compatible, but those values are ignored by the normal product path.

Need more setup detail? See [Installation](INSTALLATION.md).

## 2. Normal flow example

- Session starts
- The user asks for a task
- AICTX provides the agent with a continuity resume capsule

```bash
codex@my-repo · session #12 · awake

Resuming: parser refactor was paused after updating token tests.
Last progress: `tests/test_parser.py` passes; next step is to update error recovery cases.

────────────────────────────────
```

- Agent performs the task
- AICTX updates continuity artifacts
- Agent provides the user with a continuity summary

```bash
────────────────────────────────
AICTX summary

Context: resumed parser refactor from previous session state.
Map: RepoMap quick ok.
Saved: updated handoff and continuity state.
Validation: `pytest -q tests/test_parser.py` passed.
Next: update parser error recovery cases.
Details: last_execution_summary.md
Continuity view file: continuity-map.mmd
View continuity online: mermaid.live view
```

## 3. Inspect Continuity View Manually

```bash
aictx view --repo .
```

Default output:

```text
.aictx/reports/continuity-view.md
.aictx/reports/continuity-map.mmd
```

Not hidden memory. Reviewable operational continuity.

## Agent lifecycle in one minute

AICTX gives cooperating agents a compact, repeatable lifecycle:

- `resume --brief` can return a smaller startup payload for routine work.
- Supported integrations get runner contracts and guard triggers.
- Validation expectations are task-aware, so documentation and analysis tasks can stay advisory.
- `finalize` can surface dirty edited files without staging or committing them.
- Work State can preserve compact discarded hypotheses when an agent explicitly records an abandoned approach.
- Prior successful strategies can be used internally as bounded hints when they are relevant.

For implementation details, see [Technical overview](TECHNICAL_OVERVIEW.md). For release history, see [Changelog](https://github.com/oldskultxo/aictx/blob/main/CHANGELOG.md).

---
title: "AICTX Quickstart"
description: "Install, initialize, and inspect AICTX repo-local continuity for coding agents in the first five minutes."
---

# Quickstart

AICTX has one default experience:

```text
install -> init -> let the coding agent work
```

After setup, compatible agents run the lifecycle themselves:

```text
resume -> work -> finalize
```

## First five minutes

### 1. Install

```bash
pip install aictx
aictx install
```

`aictx install` prepares AICTX runtime metadata and optional global runner integration, such as Codex global files when `~/.codex/` is detected.

### 2. Initialize the repo

From inside the target repository:

```bash
aictx init
```

This writes repo-local AICTX state and generated agent guidance such as `AGENTS.md`, `CLAUDE.md`, GitHub Copilot instruction files, and MCP config when supported.

### 3. Verify health

```bash
aictx doctor --repo . --json
```

A fresh repo may have little continuity. That is normal. AICTX becomes useful after agents finalize real work.

### 4. Use your coding agent normally

Ask for the work you actually want:

```text
Fix the parser recovery bug and run the focused parser tests.
```

A compatible agent should:

1. call `aictx_resume` or `aictx resume --repo . --task "<goal>" --json`;
2. work normally;
3. call `aictx_finalize` or `aictx finalize --repo . --status success|failure --summary "<what happened>" --json`.

You should not need to manage AICTX manually during everyday work.

### 5. Inspect what exists

```bash
aictx view --repo .
```

Default output:

```text
.aictx/reports/continuity-view.md
.aictx/reports/continuity-map.mmd
```

## Manual lifecycle example

Use this only for inspection, unsupported runners, examples, or debugging:

```bash
aictx resume --repo . --task "fix the parser recovery bug" --json
# do work, edit files, run tests
aictx finalize --repo . --status success --summary "Fixed parser recovery and ran focused parser tests" --json
```

A later session resumes from repo-local continuity.

## What to read next

- [Installation](INSTALLATION.md): setup options.
- [What AICTX writes](WHAT-AICTX-WRITES.md): files and local/portable behavior.
- [Usage](USAGE.md): command reference.
- [Continuity View](CONTINUITY_VIEW.md): inspect current continuity.
- [Docs map](README.md): main, advanced, and legacy/internal docs tiers.

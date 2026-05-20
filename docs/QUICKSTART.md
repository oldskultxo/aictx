---
title: "AICTX Quickstart for Operational Continuity"
description: "Start using AICTX to preserve operational continuity across AI coding-agent sessions with the official aictx CLI."
---

# Quickstart

This walkthrough shows the shortest path from setup to visible operational continuity.

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

Optional check:

```bash
aictx --version
aictx doctor --repo . --json
```

A fresh repo may have little continuity. That is expected. AICTX becomes more useful after work has been finalized and Work State, failures, decisions, or handoffs exist.

### Interactive install
Installation will only ask you about enabling recommended RepoMap support using Tree-sitter.

RepoMap uses Tree-sitter to build a compact structural map of files and symbols. It helps agents choose better starting points without reading the whole repo.

### Interactive init
During initialization, you can choose from different communication modes. `disabled` is the default.

```bash
Communication modes:
- disabled: No special communication layer; agents answer normally.
- caveman_lite: Light compact mode; keeps explanations but reduces chatter.
- caveman_full: Strong compact mode; recommended if you want less runtime noise.
- caveman_ultra: Aggressive compression; shortest responses, least prose.
```

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

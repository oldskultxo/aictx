---
title: "What AICTX Writes"
description: "Inspect the repo-local and optional portable files AICTX creates during install, init, resume, finalize, and view."
---

# What AICTX writes

AICTX is local-first. Most runtime state lives in `.aictx/` inside the repository. Generated agent-instruction files live beside the tools that read them.

Do not hand-edit `.aictx/` during normal work. Use AICTX CLI or MCP tools.

## Summary table

| Action | Common writes | Local-only by default | Portable option |
|---|---|---:|---:|
| `aictx install` | Global/workspace AICTX runtime metadata; optional global Codex integration | Yes | No |
| `aictx init` | `.aictx/`, runner instruction files, MCP config, `.gitignore` managed block | Yes | Some continuity can be opt-in portable |
| `aictx resume` | `.aictx/continuity/resume_capsule.md`, `.aictx/continuity/resume_capsule.json`, session/contract traces | Yes | No |
| `aictx finalize` | handoff, decisions, execution summary, metrics, failures, Work State updates | Yes | Selected append-only continuity when enabled |
| `aictx view` | `.aictx/reports/continuity-view.md`, `.aictx/reports/continuity-map.mmd` | Yes | Follows repo portability policy |
| `aictx clean` | removes AICTX-managed repo files/blocks | N/A | N/A |

## `aictx install`

Global/runtime setup may write AICTX-managed files outside the repo, depending on options and detected tools:

- AICTX home/config state;
- workspace registry/config;
- MCP runtime metadata;
- optional global Codex integration when `~/.codex/` exists or `--install-codex-global` is passed.

It does not initialize a repository. Use `aictx init` for repo-local setup.

## `aictx init`

Common repo-local writes:

```text
.aictx/
AGENTS.md
CLAUDE.md
.github/copilot-instructions.md
.github/instructions/aictx.instructions.md
.github/prompts/
.claude/settings.json
.claude/hooks/aictx_session_start.py
.claude/hooks/aictx_user_prompt_submit.py
.claude/hooks/aictx_pre_tool_use.py
.mcp.json
.vscode/mcp.json
.gitignore
```

Exact files depend on runner detection and options such as `--no-mcp`, `--no-gitignore`, and `--portable-continuity`.

RepoMap, when enabled, can write:

```text
.aictx/repo_map/config.json
.aictx/repo_map/manifest.json
.aictx/repo_map/index.json
.aictx/repo_map/status.json
```

## `aictx resume`

`resume` is the agent-facing continuity query. It may write generated trace artifacts so the current startup context is inspectable:

```text
.aictx/continuity/resume_capsule.md
.aictx/continuity/resume_capsule.json
.aictx/continuity/session.json
.aictx/continuity/contracts/*.json
```

These are generated runtime artifacts, not hand-authored project docs.

## `aictx finalize`

`finalize` records factual evidence after work. Depending on what happened, it may update:

```text
.aictx/continuity/handoff.json
.aictx/continuity/handoffs.jsonl
.aictx/continuity/decisions.jsonl
.aictx/continuity/last_execution_summary.md
.aictx/tasks/active.json
.aictx/tasks/threads/*.json
.aictx/tasks/threads/*.events.jsonl
.aictx/failure_memory/failure_patterns.jsonl
.aictx/metrics/execution_logs.jsonl
.aictx/metrics/execution_feedback.jsonl
.aictx/metrics/contract_compliance.jsonl
```

The exact set depends on task status, observed files, commands, tests, failures, and whether there is active Work State.

## `aictx view`

`view` generates deterministic inspection output:

```text
.aictx/reports/continuity-view.md
.aictx/reports/continuity-map.mmd
```

With `aictx finalize --include-view`, finalization can also update the view and return links in the AICTX final summary.

## Local-only vs portable

Default AICTX continuity is local-only. That keeps noisy latest-run state, private execution traces, and local runner details out of Git.

Opt in to portable continuity only when you want a small team-safe subset shared through Git:

```bash
aictx init --repo . --portable-continuity
```

Portable continuity is still file-based and repo-local. Git is the transport; AICTX does not add a cloud sync service.

## Remove AICTX-managed files

Repo cleanup:

```bash
aictx clean --repo .
```

Global cleanup:

```bash
aictx uninstall
```

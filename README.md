# aictx

Portable multi-LLM context engine bootstrapper and local runtime.

## What it is

`aictx` is the distributable layer for installing a stable `.ai_context_*` contract into repositories so Codex, Claude, and other LLM agents can use local contextual memory from the moment the repo is initialized.

## Current scope

- global install config under `~/.ai_context_engine/`
- repo initialization scaffold under `.ai_context_*`
- workspace registry for cross-project discovery
- interactive and non-interactive CLI flows
- bundled starter templates for packet schema, defaults, and model routing
- first extraction lane from `ai_context_engine` into `aictx`

## Design rules

- filesystem artifacts are created by scripting/runtime, never by the LLM
- repo-local structure is eager: directories and starter files exist immediately after `aictx init`
- cross-project discovery is registry/workspace-based, not hardcoded to a machine path
- repo-local memory and global engine state are separated

## Commands

### Install globally

```bash
aictx install
```

Non-interactive:

```bash
aictx install --yes --workspace-root ~/projects
```

What it creates:

- `~/.ai_context_engine/config.json`
- `~/.ai_context_engine/projects_registry.json`
- `~/.ai_context_engine/workspaces/default.json`
- `~/.ai_context_engine/.ai_context_global_metrics/`

### Initialize a repository

```bash
aictx init
```

Non-interactive:

```bash
aictx init --repo . --yes
```

What it creates:

- `.ai_context_engine/`
- `.ai_context_memory/`
- `.ai_context_cost/`
- `.ai_context_task_memory/`
- `.ai_context_failure_memory/`
- `.ai_context_memory_graph/`
- `.ai_context_library/`
- `.context_metrics/`

### Workspace operations

```bash
aictx workspace add-root ~/projects
aictx workspace list
```

## Development

```bash
PYTHONPATH=src python3 -m aictx install --yes --workspace-root ~/projects
PYTHONPATH=src python3 -m aictx init --repo . --yes
PYTHONPATH=src python3 -m aictx workspace list
```

## Extraction status

See `docs/EXTRACTION_ROADMAP.md`.

## Migrated subsystems

Current repo-local CLI surface also exposes the migrated runtime subsystems:

- `aictx boot`
- `aictx query`
- `aictx packet`
- `aictx route`
- `aictx migrate`
- `aictx detect-stale`
- `aictx compact`
- `aictx ensure-gitignore`
- `aictx new-note`
- `aictx touch`
- `aictx failure`
- `aictx task-memory`
- `aictx memory-graph`
- `aictx library`
- `aictx global`

The repository also includes compatibility wrappers under `scripts/` and `bin/`.

# aictx

**Install once. Initialize a repo. Give coding agents a real runtime contract.**

`aictx` turns a normal repository into a repository that is prepared for coding agents.

## Product surface

The sellable user flow stays intentionally small:

1. `aictx install`
2. `aictx init`
3. use Codex, Claude Code, or your normal automation

Everything else exists to support that runtime, not to expand the primary UX.

## What it really does today

After `install + init`, `aictx` can provide:

- repo-local bootstrap memory under `.ai_context_engine/`
- packet-oriented context for non-trivial work
- task memory, failure memory, and memory graph scaffolds
- repo-native instruction integration for Codex and Claude Code
- wrapped middleware for generic automation via `aictx internal run-execution`
- local/global telemetry and health artifacts

## Honest limits

This is still a **0.x** product.

- final behavior depends on each runner honoring its instruction and hook system
- telemetry quality is best-effort unless confidence is explicitly high
- advanced/internal commands are supported, but not the main thing being sold
- some deeper capabilities are still being extracted from the canonical engine

See [docs/LIMITATIONS.md](docs/LIMITATIONS.md).

## Install once

```bash
aictx install
```

Non-interactive:

```bash
aictx install --yes --workspace-root ~/projects
```

This creates the global runtime under `~/.ai_context_engine/` and provisions:

- global configuration
- workspace registry
- adapters and wrappers
- global telemetry storage
- global Codex instructions

## Initialize a repo

```bash
aictx init
```

Non-interactive:

```bash
aictx init --repo . --yes
```

`init` creates:

- `.ai_context_engine/memory/`
- `.ai_context_engine/cost/`
- `.ai_context_engine/task_memory/`
- `.ai_context_engine/failure_memory/`
- `.ai_context_engine/memory_graph/`
- `.ai_context_engine/library/`
- `.ai_context_engine/metrics/`
- `.ai_context_engine/adapters/`
- `.ai_context_engine/state.json`
- `.ai_context_engine/agent_runtime.md`

And native repo integration files:

- `AGENTS.md`
- `AGENTS.override.md`
- `CLAUDE.md`
- `.claude/settings.json`
- `.claude/hooks/...`
- `.gitignore`

## Runtime consistency

`aictx boot --repo <path>` and `aictx execution prepare ...` now expose:

- effective communication policy
- communication source precedence
- runtime consistency checks between repo preferences and repo state

Precedence is:

`explicit user instruction > repo prefs > global defaults > hardcoded fallback`

## Development quickstart

```bash
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -e . pytest build
make test
make smoke
make package-check
```

You can also call the installed script directly:

```bash
.venv/bin/aictx --help
```

## Read next

- [Usage guide](docs/USAGE.md)
- [Technical overview](docs/TECHNICAL_OVERVIEW.md)
- [5-minute demo](docs/DEMO.md)
- [Current limitations](docs/LIMITATIONS.md)
- [Phase 2 notes](docs/PHASE2_NOTES.md)
- [Release checklist](docs/RELEASE_CHECKLIST.md)

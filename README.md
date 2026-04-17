# aictx

**Install once. Initialize a repo. Give coding agents a real runtime contract.**

`aictx` turns a normal repository into a repository with a **runtime contract for coding agents**.

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

The strongest value today is:

- repo-native runtime contract
- runner-aware execution discipline
- structured local persistence

The contextual layer is real, but still mostly heuristic rather than deeply intelligent.

## Honest limits

This is still a **0.x beta** product.

- final behavior depends on each runner honoring its instruction and hook system
- telemetry quality is best-effort unless confidence is explicitly high
- advanced/internal commands are supported, but not the main thing being sold
- current task routing, ranking, graph expansion, and packet building are mostly deterministic heuristics

See [docs/LIMITATIONS.md](docs/LIMITATIONS.md).

## Install from PyPI

```bash
pip install aictx
```

Then:

```bash
aictx install
aictx init --repo .
```

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

## What to expect from the contextual core

Today `aictx` is better understood as:

- **primary**: runtime contract + execution discipline + repo bootstrap
- **secondary**: heuristic packet, memory, failure, and graph accelerators

That means the product already adds structure and reuse, but it does **not** yet claim deep repo understanding beyond deterministic retrieval and bounded heuristics.

## Public beta posture

`aictx` is now distributed publicly as a **beta 0.x** package.

- installation is supported through PyPI and GitHub releases
- the core user flow is `pip install aictx` -> `aictx install` -> `aictx init`
- compatibility is still best-effort, not a long-term 1.0 stability promise

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

Public release validation also checks clean wheel installation, not just editable installs.

## Read next

- [Usage guide](docs/USAGE.md)
- [Technical overview](docs/TECHNICAL_OVERVIEW.md)
- [5-minute demo](docs/DEMO.md)
- [Current limitations](docs/LIMITATIONS.md)
- [Phase 2 notes](docs/PHASE2_NOTES.md)
- [Release checklist](docs/RELEASE_CHECKLIST.md)

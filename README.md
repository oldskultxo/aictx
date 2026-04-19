# aictx

Most coding agents forget important repo context between sessions.

`aictx` turns a normal repository into one with a **runtime contract for coding agents** so repeated work is reduced and behavior is more consistent.

---

If you use coding agents (Codex, Claude Code, or similar), this is common:

- you explain the same thing over and over
- past decisions are not reused consistently
- context gets expensive fast
- many tasks feel like starting from zero

`aictx` addresses that by making the repository itself agent-aware.

Not by adding more prompt templates.  
Not by replacing your agent.  
By giving the repo a persistent runtime layer for execution and reuse.

---

After `aictx install` + `aictx init`, your repo gets:

- a runtime contract for agent execution
- structured repo-local memory reuse across tasks
- more consistent run-to-run behavior
- automatic prepare/finalize middleware with telemetry + learning write-back

You keep using your agent normally.  
`aictx` adds structure and reuse; results still vary by runner behavior and task ambiguity.

---

This is not:

- a prompt template
- an agent framework
- a wrapper that replaces Codex or Claude

This is:

- a repo-level runtime for coding agents

---

## Quick start

```bash
pip install aictx
aictx install
cd your-repo
aictx init
```

Then use your coding agent as usual.

---

## Status

`aictx` is currently in **beta (0.x)**.

It is designed to be:

- minimal on the surface
- structured internally
- explicit about limitations

It does not try to replace your agent.  
It helps your agent operate with a repo-native runtime contract.

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
- telemetry/reporting should be treated as execution trace and observed runtime activity, not synthetic performance proof
- when real measurement is missing, prefer `unknown` over inferred improvement claims
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

## Benchmark status

The previous synthetic A/B/C benchmark flow was removed from the public product path.

- it produced deterministic simulated metrics
- it is not valid evidence for external performance claims
- historical code now lives under `experiments/simulated/benchmark.py`

See `experiments/simulated/BENCHMARK_QUICKSTART.md` for historical non-product benchmark notes.

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
- [Historical benchmark notes](experiments/simulated/BENCHMARK_QUICKSTART.md)
- [Phase 2 notes](docs/PHASE2_NOTES.md)
- [Release checklist](docs/RELEASE_CHECKLIST.md)

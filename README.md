# aictx

Coding agents forget how they worked.

aictx makes their past executions reusable.

It records real execution, stores useful patterns, and reuses successful strategies in later executions inside the same repository.

---

## Why this exists

Most agent workflows start from scratch every time.

aictx allows them to reuse what already worked.

---

## What aictx is

A repo-local execution memory layer for coding agents that records real execution and reuses successful strategies.

- repo-local execution memory
- real execution logging
- reusable strategy memory
- lightweight runtime guidance for coding agents

---

## Safety model

AICTX modifies repository files and can optionally install runner integrations.
By default it creates repo-local runtime artifacts only during repo setup, and `aictx install` does not modify global Codex files.
Global Codex integration requires `aictx install --install-codex-global`.

---

## Quick start

```bash
pip install aictx
aictx install
cd your-repo
aictx init
```

After `aictx init`, you can use your coding agent normally in that repo.

Manual `aictx` commands after initialization are optional:
- the intended flow is `install` + `init`, then agent-driven usage
- `suggest`, `reflect`, `reuse`, and `report real-usage` remain available for inspection, debugging, or manual control
- Claude/Codex integration files and hooks added by `init` are there to help the agent use `aictx` automatically when the runner respects repo instructions

---

## Public CLI

```bash
aictx install
aictx init
aictx suggest
aictx reflect
aictx reuse
aictx report real-usage
aictx clean
aictx uninstall
```

Only `install` and `init` are part of the normal setup path.

The rest of the public commands are optional operational commands:
- `suggest`, `reflect`, `reuse` -> for manual inspection or explicit agent calls
- `report real-usage` -> for reviewing stored execution data
- `clean`, `uninstall` -> for removing AICTX-managed content

---

## What aictx does

* records real execution in `.ai_context_engine/metrics/execution_logs.jsonl`
* writes operational feedback in `.ai_context_engine/metrics/execution_feedback.jsonl`
* stores successful and failed strategies in `.ai_context_engine/strategy_memory/strategies.jsonl`
* reuses only successful strategies during later executions
* exposes small JSON commands for runtime guidance

---

## What AICTX modifies

Repo-local:
- `.ai_context_engine/`
- AICTX-managed blocks in `AGENTS.md`, `AGENTS.override.md`, and `CLAUDE.md`
- `.claude/settings.json` merged AICTX hook entries
- `.claude/hooks/aictx_*.py`
- `.gitignore` entries for AICTX runtime paths

Optional global:
- `~/.codex/AGENTS.override.md`
- `~/.codex/config.toml`

Global Codex files are only updated when `--install-codex-global` is passed.

---

## Idempotency guarantees

- `aictx init` is non-destructive for existing AICTX execution logs and strategy memory
- existing `.ai_context_engine/metrics/*.jsonl` and `.ai_context_engine/strategy_memory/*.jsonl` files are preserved
- `.claude/settings.json` is merged, not overwritten
- AICTX-managed Markdown blocks and hooks are idempotent
- `aictx init` does not delete legacy non-AICTX paths

---

## What aictx does NOT do

aictx does not optimize your agent.
aictx does not guarantee better performance.

It makes past executions observable and reusable.

---

## Who this is for

- engineers using coding agents repeatedly in the same repository
- teams that want repo-local execution history and reusable strategies
- users who prefer traceable artifacts over heuristic-heavy automation

## Who this is not for

- users expecting guaranteed productivity gains
- teams looking for a full orchestration platform
- workflows that do not preserve repo-level instructions or execution discipline

---

## Runtime loop

1. `prepare_execution()` loads prior successful strategies and may attach `execution_hint`
2. the agent executes
3. `finalize_execution()` records logs, feedback, and strategy memory
4. the next execution can reuse successful strategies and ignore failed ones

---

## Main runtime artifacts

```text
.ai_context_engine/
  metrics/
    execution_logs.jsonl
    execution_feedback.jsonl
  strategy_memory/
    strategies.jsonl
```

---

## Additional properties

* repo-local artifacts are the source of truth; execution history and strategy memory stay inspectable inside the repository
* failed strategies are stored, but they are excluded from reuse by default
* public command outputs are deterministic and machine-readable JSON
* AICTX-managed changes can be removed cleanly with `aictx clean` and `aictx uninstall`

---

## Notes

* file tracking depends on explicit input from the agent/runtime
* strategy reuse is heuristic: matching task type and overlapping files are preferred, with recency as a secondary signal
* task typing uses explicit metadata first, then deterministic keyword/path inference, then `unknown`
* middleware packet generation is not active in the default runtime path
* failed strategies are stored but never reused as hints
* no synthetic benchmarks or estimated improvements are reported

---

## Cleanup

* `aictx clean` removes only AICTX-managed content from the current repository: the `.ai_context_engine/` scaffold, AICTX blocks in `AGENTS.md` / `AGENTS.override.md` / `CLAUDE.md`, AICTX Claude hooks/settings, and the `.gitignore` entry added by AICTX
* `aictx uninstall` removes AICTX-managed content from all registered repositories and removes global AICTX state under `~/.ai_context_engine`, plus AICTX-managed Codex global instructions/config lines
* both commands are conservative: they only remove content that AICTX created or marked as AICTX-managed

---

## Possible evolution

The current v1 keeps strategy memory intentionally simple.

Possible future work, based on real usage:

* better file access capture from agent/runtime integrations
* more precise strategy matching beyond task type
* clearer comparison across repeated task categories
* stronger runner-native automation where supported
* richer repo-level reporting built only from real execution history

Not part of the current product contract:

* synthetic benchmarks
* heuristic scores
* guaranteed optimization claims

---

## Read next

* [Usage](docs/USAGE.md)
* [Demo](docs/DEMO.md)
* [Limitations](docs/LIMITATIONS.md)
* [Safety](docs/SAFETY.md)
* [Upgrade](docs/UPGRADE.md)

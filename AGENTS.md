# AGENTS Instructions for `aictx`

- `aictx` is the distributable multi-LLM installer/runtime layer for `.ai_context_*`.
- Local filesystem artifacts are created by scripting/runtime, never by the LLM.
- Prefer eager scaffold semantics: structure exists immediately after `aictx init`.
- Cross-project behavior must come from workspace registry/config, never hardcoded machine paths.
- For subsystem changes, validate with `python3 -m aictx migrate`, `boot`, `query`, `packet`, `memory-graph --refresh`, and `global --refresh --health-check --json` when relevant.

<!-- AICTX:START -->
## AI Context Engine

This repository is initialized for `aictx`.

Agent rules:
- Enter the runtime middleware for every execution in initialized repos.
- Use repo-local execution history and strategy memory before deeper repo analysis.
- Do not hand-edit generated `.ai_context_*` artifacts.
- Before opening more than 3 files: run `aictx suggest --repo .`
- If you reopen the same file: run `aictx reflect --repo .`
- If the task seems similar to a previous one: run `aictx reuse --repo .`
- If you are unsure about the next step: run `aictx suggest --repo .`

Detailed runtime instructions:
- `.ai_context_engine/agent_runtime.md`
<!-- AICTX:END -->

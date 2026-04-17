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
- Read `.ai_context_engine/memory/derived_boot_summary.json` first when present.
- Use `aictx` as the first low-cost memory layer before deeper repo analysis.
- Apply `.ai_context_engine/memory/user_preferences.json` as defaults unless the current prompt overrides them.
- Enter the engine middleware for every execution in initialized repos, not only when a skill is active.
- Communication mode may be disabled by repo-local preferences; explicit user requests still override for the current session.
- Persist validated learnings after non-trivial tasks.
- If the user asks the agent to learn docs, reusable knowledge, or external references, activate the knowledge/library workflow.
- If the user asks for savings reports or health, use repo-local `.ai_context_engine/metrics/` and global engine telemetry artifacts as the source of truth.
- Missing telemetry must be reported as `unknown`, never as zero or as an invented estimate.
- Do not hand-edit generated `.ai_context_*` artifacts.

Detailed runtime instructions:
- `.ai_context_engine/agent_runtime.md`
<!-- AICTX:END -->

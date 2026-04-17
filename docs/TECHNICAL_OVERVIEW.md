# Technical overview

## Product model

`aictx` is intentionally split into:

- **human surface**
  - `aictx install`
  - `aictx init`
- **runtime/internal surface**
  - bootstrap
  - packet
  - query
  - middleware prepare/finalize
  - health and global metrics

## Preference precedence

Runtime communication policy uses one precedence model everywhere:

1. explicit user instruction
2. repo-local preferences
3. global defaults
4. hardcoded fallback

`boot` and `execution prepare` expose the effective result plus source metadata.

## Repo-local runtime

Repo-local state lives under `.ai_context_engine/`.

Primary runtime files:

- `.ai_context_engine/memory/user_preferences.json`
- `.ai_context_engine/state.json`
- `.ai_context_engine/agent_runtime.md`

## Consistency hardening

`aictx` now checks for contradictions between:

- repo-local preferences
- repo-local state
- effective communication policy reported by runtime endpoints

Missing data is reported as `not_initialized` or `unknown` instead of being silently treated as healthy.

## Integration model

- **Codex**: `AGENTS.md` + `AGENTS.override.md` + repo runtime contract
- **Claude Code**: `CLAUDE.md` + `.claude/settings.json` + project hooks
- **Generic automation**: `aictx internal run-execution`

## Code structure

The runtime is still evolving, but product-hardening logic is now being split out of the monolith into focused modules such as `runtime_contract.py` so communication policy and consistency checks are owned in one place.

## Global health checks

Global health checks now include runtime-consistency reporting per project so state drift is visible during cross-project validation.

# Extraction roadmap from `ai_context_engine` to `aictx`

## Goal

Move the distributable installer, repo scaffold, and multi-LLM bootstrap contract into `aictx`, while leaving the canonical note corpus and current runtime evolution inside `ai_context_engine` until each subsystem is ported.

## Already extracted

- distributable repo scaffold
- install/init product surface
- bundled starter templates for:
  - `context_packet_schema.json`
  - `user_preferences.json`
  - `model_routing.json`
- repo-local `.ai_context_*` contract generation
- native runner integration provisioning for Codex and Claude Code
- wrapped execution entrypoint for generic automation

## Next extraction slices

1. harden native runner integrations
2. boot + health commands
3. query + packet generation
4. failure memory
5. task memory
6. memory graph
7. library ingestion and retrieval
8. optional global metrics aggregation

## Rules

- `aictx` owns distributable runtime, installer UX, and bundled templates.
- `aictx` human-facing product surface should remain `install + init`.
- `ai_context_engine` remains the current canonical lab/runtime until a slice is fully ported.
- no absolute machine paths in bundled templates.
- no LLM-created filesystem artifacts; all scaffolding remains script-owned.

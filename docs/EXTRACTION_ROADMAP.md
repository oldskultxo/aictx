# Extraction roadmap from `ai_context_engine` to `aictx`

## Goal

Move the distributable installer, repo scaffold, and multi-LLM bootstrap contract into `aictx`, while leaving the canonical note corpus and current runtime evolution inside `ai_context_engine` until each subsystem is ported.

## Already extracted

- distributable repo scaffold
- install/init/workspace CLI surface
- bundled starter templates for:
  - `context_packet_schema.json`
  - `user_preferences.json`
  - `model_routing.json`
- repo-local `.ai_context_*` contract generation

## Next extraction slices

1. boot + health commands
2. query + packet generation
3. failure memory
4. task memory
5. memory graph
6. library ingestion and retrieval
7. optional global metrics aggregation

## Rules

- `aictx` owns distributable runtime, installer UX, and bundled templates.
- `ai_context_engine` remains the current canonical lab/runtime until a slice is fully ported.
- no absolute machine paths in bundled templates.
- no LLM-created filesystem artifacts; all scaffolding remains script-owned.

# Extraction roadmap from `aictx` to `aictx`

## Goal

Move the distributable installer, repo scaffold, and multi-LLM bootstrap contract into `aictx`, while leaving the canonical note corpus and current runtime evolution inside `aictx` until each subsystem is ported.

## Already extracted

- distributable repo scaffold
- install/init product surface
- bundled starter templates for:
  - `context_packet_schema.json`
  - `user_preferences.json`
  - `model_routing.json`
- repo-local `.aictx_*` contract generation
- native runner integration provisioning for Codex and Claude Code
- wrapped execution entrypoint for generic automation

## Next extraction slices

1. harden native runner integrations
2. boot + health commands
3. query + packet generation
4. failure memory
5. task memory
6. memory graph
7. repo-native `.aictx/memory/source/` knowledge ingestion
8. runtime telemetry grounded only in per-repo real execution data

## Rules

- `aictx` owns distributable runtime, installer UX, and bundled templates.
- `aictx` human-facing product surface should remain `install + init`.
- `aictx` remains the current canonical lab/runtime until a slice is fully ported.
- no absolute machine paths in bundled templates.
- no LLM-created filesystem artifacts; all scaffolding remains script-owned.

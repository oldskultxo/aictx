<!-- AICTX:START -->
## AICTX repo-native Codex instructions

- This repository is initialized with `aictx`; prefer `.ai_context_engine/` as the first memory/runtime layer.
- Read `.ai_context_engine/agent_runtime.md` before deep repo analysis when the task is non-trivial.
- Read `CLAUDE.md` too when it exists; it is part of the repo-level AICTX runtime contract.
- For non-trivial work, prefer packet-oriented context from `aictx packet --task "<task>"`.
- Do not hand-edit generated `.ai_context_engine/*` artifacts.
- Do not recreate parallel memory folders like `.ai_context_memory` or `.ai_context_task_memory`.
- After meaningful writes, prefer `aictx memory-graph --refresh` and `aictx global --refresh`.
- When running wrapped automations, prefer `aictx internal run-execution` as the middleware entrypoint.
- Persist learnings through the engine flow rather than inventing parallel memory files.
<!-- AICTX:END -->

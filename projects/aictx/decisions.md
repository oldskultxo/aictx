---
priority: important
confidence: high
last_verified: 2026-04-16
tags: aictx, architecture, decisions, memory_system
---

# aictx: decisions

- `aictx` owns the distributable installer/runtime surface for multi-LLM use.
- Local `.ai_context_*` structure is eager at repo init time, not lazy.
- Filesystem artifacts are created by scripts/runtime, never by the LLM.
- Cross-project discovery is workspace-registry based, not tied to a machine-specific path.

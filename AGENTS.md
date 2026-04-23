# AGENTS Instructions for `aictx`

- `aictx` is the distributable multi-LLM installer/runtime layer for `.aictx_*`.
- Local filesystem artifacts are created by scripting/runtime, never by the LLM.
- Prefer eager scaffold semantics: structure exists immediately after `aictx init`.
- Cross-project behavior must come from workspace registry/config, never hardcoded machine paths.
- For subsystem changes, validate with `python3 -m aictx migrate`, `boot`, `query`, `packet`, `memory-graph --refresh`, and `global --refresh --health-check --json` when relevant.

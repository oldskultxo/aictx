# AGENTS Instructions for `aictx`

- `aictx` is the distributable multi-LLM installer/runtime layer for `.aictx_*`.
- Local filesystem artifacts are created by scripting/runtime, never by the LLM.
- Prefer eager scaffold semantics: structure exists immediately after `aictx init`.
- Cross-project behavior must come from workspace registry/config, never hardcoded machine paths.
- For subsystem changes, validate with `python3 -m aictx internal migrate`, `internal boot`, `internal query`, `internal packet`, `internal memory-graph --refresh`, and `report real-usage --repo <repo>` when relevant.

<!-- AICTX:START -->
## AI Context Engine

This repository is initialized for `aictx`.

Agent rules:
- Enter the runtime middleware for every execution in initialized repos.
- If `prepare_execution` returns `startup_banner_text`, show it once at the start of the first user-visible response for the visible session.
- After finalize, append `agent_summary_text` verbatim to the final user response.
- If no finalize output exists, say `AICTX summary unavailable`.
- In the `aictx` source repository, prefer `PYTHONPATH=src .venv/bin/python -m aictx ...` over a globally installed `aictx` binary so the current checkout drives the runtime.
- Use repo-local execution history and strategy memory before deeper repo analysis.
- `.aictx/memory/source/` is editable source knowledge; do not hand-edit generated derived artifacts under `.aictx/boot`, `.aictx/store`, `.aictx/indexes`, `.aictx/metrics`, and similar runtime folders.
- Before opening more than 3 files: run `aictx suggest --repo .`
- If you reopen the same file: run `aictx reflect --repo .`
- If the task seems similar to a previous one: run `aictx reuse --repo .`
- If you are unsure about the next step: run `aictx suggest --repo .`

Detailed runtime instructions:
- `.aictx/agent_runtime.md`
<!-- AICTX:END -->

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
- On the first execution of each visible session, always show the startup banner at the start of the first user-visible response. If `prepare_execution` returns `startup_banner_text`, render the startup banner in the current user language. Prefer structured render payloads when available, and you may fully rephrase human-readable prose from structured factual fields while preserving exact facts, file paths, commands, flags, package names, test names, code identifiers, and other technical tokens; do not add, remove, reorder, reinterpret, or invent facts. If first-session text is missing, render `{agent_label} · session #{session_count} · awake` from prepared identity fields. Do not render it again after `already_shown` is true.
- After finalize, append the AICTX final summary to the final user response, using `agent_summary_text` as the canonical compact user-facing source, localized to the current user language from structured factual fields when available while preserving exact facts, technical tokens, and the details link/path.
- If no finalize output exists, say `AICTX summary unavailable`.
- In the `aictx` source repository, prefer `PYTHONPATH=src .venv/bin/python -m aictx ...` over a globally installed `aictx` binary so the current checkout drives the runtime.
- Use repo-local execution history and strategy memory before deeper repo analysis.
- `.aictx/memory/source/` is editable source knowledge; do not hand-edit generated derived artifacts under `.aictx/boot`, `.aictx/store`, `.aictx/indexes`, `.aictx/metrics`, and similar runtime folders.
- Use `prepared.runtime_text_policy`, `prepared.startup_banner_policy`, and `finalized.agent_summary_policy` when available.
- You may enrich AICTX-originated user-visible texts if helpful, but you must preserve real facts and never invent missing data.
- Before opening more than 3 files: run `aictx suggest --repo .`
- If you reopen the same file: run `aictx reflect --repo .`
- If the task seems similar to a previous one: run `aictx reuse --repo .`
- If you are unsure about the next step: run `aictx suggest --repo .`

Detailed runtime instructions:
- `.aictx/agent_runtime.md`
<!-- AICTX:END -->

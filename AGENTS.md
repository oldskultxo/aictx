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
- The AICTX lifecycle remains `prepare/startup context → resume capsule → work → finalize → final AICTX summary/persistence`.
- At session start, run exactly one AICTX continuity command: `aictx resume --repo . --request "<current user request>"`.
- Use the returned continuity capsule as the operational brief and use its `startup_banner_text`/`startup_banner_render_payload` as the startup banner source during normal agent startup.
- `resume` is the canonical agent-facing continuity query; it does not replace `prepare_execution`, `finalize_execution`, the startup banner, the final AICTX summary, or persistence.
- Do not inspect `.aictx/`.
- Do not run exploratory AICTX commands.
- Do not run `aictx internal`, `aictx -h`, `aictx reuse`, `aictx suggest`, `aictx next`, `aictx task`, `aictx messages`, `aictx reflect`, or `aictx report` during normal task startup unless the user asks for AICTX diagnostics, the task is about AICTX itself, resume is missing/corrupt/contradictory, or finalization/update lifecycle requires it.
- On the first execution of each visible session, always show the startup banner at the start of the first user-visible response. If `prepare_execution` returns `startup_banner_text`, render the startup banner in the current user language. When `prepared.startup_banner_policy.render_payload_field` points to `prepared.startup_banner_render_payload`, prefer that structured payload for localization and use `prepared.startup_banner_text` only as the compact fallback source. You may fully rephrase human-readable prose from structured factual fields while preserving exact facts, file paths, commands, flags, package names, test names, code identifiers, and other technical tokens; do not add, remove, reorder, reinterpret, or invent facts. If first-session text is missing, render `{agent_label} · session #{session_count} · awake` from prepared identity fields. Do not render it again after `already_shown` is true.
- After finalize, append the AICTX final summary to the final user response, using `agent_summary_text` as the compact fallback user-facing source. When `agent_summary_policy.render_payload_field` points to `agent_summary_render_payload`, prefer that structured payload for localization while preserving exact facts, technical tokens, and the details link/path.
- If no finalize output exists, say `AICTX summary unavailable`.
- In the `aictx` source repository, prefer `PYTHONPATH=src .venv/bin/python -m aictx ...` over a globally installed `aictx` binary so the current checkout drives the runtime.
- Use the `aictx resume` capsule before deeper repo analysis.
- `.aictx/memory/source/` is editable source knowledge; do not hand-edit generated derived artifacts under `.aictx/boot`, `.aictx/store`, `.aictx/indexes`, `.aictx/metrics`, and similar runtime folders.
- Use `prepared.runtime_text_policy`, `prepared.startup_banner_policy`, and `finalized.agent_summary_policy` when available.
- You may enrich AICTX-originated user-visible texts if helpful, but you must preserve real facts and never invent missing data.
- Advanced/diagnostic/building-block commands remain available for humans and diagnostics, but normal agents should not use them during startup.

Detailed runtime instructions:
- `.aictx/agent_runtime.md`
<!-- AICTX:END -->

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
- At session start, run exactly one AICTX continuity command: `aictx resume --repo . --request "<current user request>" --json`.
- After task work, run exactly one AICTX finalization command: `aictx finalize --repo . --status success|failure --summary "<what happened>" --json`.
- Use the returned continuity capsule as the operational brief during normal agent startup.
- Render exactly one startup banner source: normal agent startup uses `resume.startup_banner_text` or `resume.startup_banner_render_payload`; wrapped execution uses `prepare_execution().startup_banner_text` or `prepare_execution().startup_banner_render_payload`. Do not render both.
- `resume` is the canonical agent-facing continuity query; it does not replace `prepare_execution`, `aictx finalize`, the startup banner, the final AICTX summary, or persistence.
- Do not inspect `.aictx/`.
- Do not run exploratory AICTX commands.
- Do not run `aictx internal`, `aictx -h`, `aictx reuse`, `aictx suggest`, `aictx next`, `aictx task`, `aictx messages`, `aictx reflect`, or `aictx report` during normal task startup unless the user asks for AICTX diagnostics, the task is about AICTX itself, resume is missing/corrupt/contradictory, or finalization/update lifecycle requires it.
- On the first execution of each visible session, always show the startup banner at the start of the first substantive user-visible response; do not consume it with a transient progress/status message that will be omitted from the final task response. Render the selected resume/prepare startup banner in the current user language. When the selected startup banner policy points to a structured render payload, prefer that structured payload for localization and use compact text only as the fallback source. You may fully rephrase human-readable prose from structured factual fields while preserving exact facts, file paths, commands, flags, package names, test names, code identifiers, and other technical tokens; do not add, remove, reorder, reinterpret, or invent facts. If first-session text is missing, render `{agent_label} · session #{session_count} · awake` from selected identity fields. Do not render it again after `already_shown` is true.
- Use `aictx finalize --repo . --status success|failure --summary "<what happened>" --json` for normal agent finalization. `finalize_execution` is the middleware API behind that command; do not call it directly from the shell. Do not run `aictx internal execution finalize` during normal task flow.
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

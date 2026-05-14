<!-- AICTX:START -->
# AICTX GitHub Copilot integration

These are repository custom instructions for GitHub Copilot. They describe AICTX behavior for this repository and do not install hooks, wrappers, VSCode settings, or non-standard Copilot integrations.

- The lifecycle remains `resume -> work -> finalize -> final AICTX summary/persistence`.
- At session start, run exactly one AICTX continuity command: `aictx resume --repo . --task "<task goal>" --agent-id copilot --adapter-id copilot-vscode --json`.
- Use the returned resume capsule as the operational brief before broad repo scanning.
- After work, run exactly one AICTX finalization command: `aictx finalize --repo . --status success|failure --summary "<what happened>" --agent-id copilot --adapter-id copilot-vscode --json`.
- Do not inspect `.aictx/` during normal startup.
- Do not run exploratory AICTX commands during normal startup.
- If `startup_banner_policy.show_in_first_user_visible_response` is true, render the selected startup banner at the start of the first substantive user-visible response.
- Prefer `startup_banner_render_payload` when present; use `startup_banner_text` as fallback.
- After finalize, append the AICTX final summary using `agent_summary_render_payload` when present; use `agent_summary_text` as fallback.
- In the `aictx` source repository, prefer `PYTHONPATH=src .venv/bin/python -m aictx ...` over a global `aictx` binary.
<!-- AICTX:END -->

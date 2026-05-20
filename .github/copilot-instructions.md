<!-- AICTX:START -->
# AICTX GitHub Copilot integration

These are repository custom instructions for GitHub Copilot. AICTX cannot force Copilot to run commands, but Copilot should follow this lifecycle whenever command execution is available.

Critical lifecycle:
- Prefer AICTX MCP tools when available; fall back to AICTX CLI commands otherwise.
- For non-trivial repository tasks, first run exactly once: `aictx resume --repo . --task "<task goal>" --agent-id copilot --adapter-id copilot-vscode --json`.
- Use the returned resume capsule as the operational brief before broad repo scanning.
- Before the final response, run exactly once: `aictx finalize --repo . --status success|failure --summary "<what happened>" --agent-id copilot --adapter-id copilot-vscode --json`.
- Append the AICTX final summary from finalize when available. Render every provided summary section, including `details`, `continuity_view_file`, and `continuity_view_online`; preserve Continuity View file links and Mermaid online view links; do not replace URLs with placeholders and do not manually reconstruct or retype pako URLs. If command execution is unavailable, say that the AICTX lifecycle could not be executed.
- Do not inspect `.aictx/` directly during normal startup; use `aictx resume`.
- Do not run exploratory AICTX commands during normal startup.
- In the `aictx` source repository, prefer `PYTHONPATH=src .venv/bin/python -m aictx ...` over a global `aictx` binary.

Verification tip: in Copilot Chat, expand response References and confirm `.github/copilot-instructions.md` is listed.
<!-- AICTX:END -->

<!-- AICTX:START -->
# AICTX GitHub Copilot integration

These are repository custom instructions for GitHub Copilot. AICTX cannot force Copilot to run commands, but Copilot should follow this lifecycle whenever command execution is available.

Critical lifecycle:
- Prefer AICTX MCP tools when available; fall back to AICTX CLI commands otherwise.
- MCP-first startup: if AICTX MCP tools are already visible, use those tools for resume/finalize. If they are not visible but `.mcp.json` or `.vscode/mcp.json` exists, have the runner attach/start the configured stdio MCP server before the first AICTX command of each new session. If MCP tools still are not attached, state that MCP config exists but tools are unavailable in this runner and use the CLI fallback.
- For non-trivial repository tasks, first run exactly once: `aictx resume --repo . --task "<task goal>" --agent-id copilot --adapter-id copilot-vscode --json`.
- Use the returned resume capsule as the operational brief before broad repo scanning.
- Before the final response, run exactly once: `aictx finalize --repo . --status success|failure --summary "<what happened>" --agent-id copilot --adapter-id copilot-vscode --json`.
- Append the AICTX final summary from finalize when available. Render every provided summary section, including `details`, `continuity_view_file`, and `continuity_view_online`; preserve Continuity View file links and Mermaid online view links; do not replace URLs with placeholders and do not manually reconstruct or retype pako URLs. If command execution is unavailable, say that the AICTX lifecycle could not be executed.
- Do not inspect `.aictx/` directly during normal startup; use `aictx resume`.
- Do not run exploratory AICTX commands during normal startup.

Verification tip: in Copilot Chat, expand response References and confirm `.github/copilot-instructions.md` is listed.
<!-- AICTX:END -->

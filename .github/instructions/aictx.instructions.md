---
applyTo: "**/*"
---

<!-- AICTX:START -->
# AICTX Copilot path-specific lifecycle

Apply these instructions to repository work. Prefer AICTX MCP tools when available; fall back to AICTX CLI commands otherwise. They intentionally duplicate the minimal AICTX lifecycle because Copilot support varies by surface.

- MCP-first startup: if AICTX MCP tools are already visible, use those tools for resume/finalize. If they are not visible but `.mcp.json` or `.vscode/mcp.json` exists, have the runner attach/start the configured stdio MCP server before the first AICTX command of each new session. If MCP tools still are not attached, state that MCP config exists but tools are unavailable in this runner and use the CLI fallback.
- Start non-trivial repository tasks with: `aictx resume --repo . --task "<task goal>" --agent-id copilot --adapter-id copilot-vscode --json`.
- Use the resume capsule before broad repo scanning.
- Finalize non-trivial repository tasks with: `aictx finalize --repo . --status success|failure --summary "<what happened>" --agent-id copilot --adapter-id copilot-vscode --json`.
- Append the AICTX final summary from finalize when available. Render every provided summary section, including `details`, `continuity_view_file`, and `continuity_view_online`; preserve Continuity View file links and Mermaid online view links; do not replace URLs with placeholders and do not manually reconstruct or retype pako URLs.
- If command execution is unavailable, state that the AICTX lifecycle could not be executed.
- Do not inspect `.aictx/` directly during normal startup.
<!-- AICTX:END -->

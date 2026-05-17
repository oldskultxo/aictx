---
applyTo: "**/*"
---

<!-- AICTX:START -->
# AICTX Copilot path-specific lifecycle

Apply these instructions to repository work. They intentionally duplicate the minimal AICTX lifecycle because Copilot support varies by surface.

- Start non-trivial repository tasks with: `aictx resume --repo . --task "<task goal>" --agent-id copilot --adapter-id copilot-vscode --json`.
- Use the resume capsule before broad repo scanning.
- Finalize non-trivial repository tasks with: `aictx finalize --repo . --status success|failure --summary "<what happened>" --agent-id copilot --adapter-id copilot-vscode --json`.
- Append the AICTX final summary from finalize when available. Render every provided summary section, including `details`, `continuity_view_file`, and `continuity_view_online`; preserve Continuity View file links and Mermaid online view links; do not replace URLs with placeholders and do not manually reconstruct or retype pako URLs.
- If command execution is unavailable, state that the AICTX lifecycle could not be executed.
- Do not inspect `.aictx/` directly during normal startup.
<!-- AICTX:END -->

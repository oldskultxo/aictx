<!-- AICTX:START -->
# AICTX finalize prompt

Use this prompt before the final response for a non-trivial GitHub Copilot repository task.

1. Summarize what happened factually.
2. Run:

```bash
aictx finalize --repo . --status success|failure --summary "<what happened>" --agent-id copilot --adapter-id copilot-vscode --json
```

3. Append the AICTX final summary when available. Render every provided summary section, including `details`, `continuity_view_file`, and `continuity_view_online`; preserve Continuity View file links and Mermaid online view links; do not replace URLs with placeholders and do not manually reconstruct or retype pako URLs.
4. If finalize cannot run, say that the AICTX lifecycle could not be completed.
<!-- AICTX:END -->

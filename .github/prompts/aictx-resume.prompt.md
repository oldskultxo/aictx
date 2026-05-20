<!-- AICTX:START -->
# AICTX resume prompt

Use this prompt when starting a non-trivial GitHub Copilot repository task.

1. Extract the task goal from the user request.
2. If AICTX MCP tools are already visible, use the MCP resume tool. If they are not visible but `.mcp.json` or `.vscode/mcp.json` exists, have the runner attach/start the configured stdio MCP server before falling back.
3. If MCP tools are unavailable, run:

```bash
aictx resume --repo . --task "<task goal>" --agent-id copilot --adapter-id copilot-vscode --json
```

4. Use the returned capsule as the operational brief before broad repo scanning.
5. Do not inspect `.aictx/` directly during normal startup.
<!-- AICTX:END -->

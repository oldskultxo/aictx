<!-- AICTX:START -->
# AICTX resume prompt

Use this prompt when starting a non-trivial GitHub Copilot repository task.

1. Extract the task goal from the user request.
2. Run:

```bash
aictx resume --repo . --task "<task goal>" --agent-id copilot --adapter-id copilot-vscode --json
```

3. Use the returned capsule as the operational brief before broad repo scanning.
4. Do not inspect `.aictx/` directly during normal startup.
<!-- AICTX:END -->

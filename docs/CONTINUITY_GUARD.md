---
title: "Continuity Guard"
description: "Read-only action-boundary checks for repo-local AICTX continuity alignment."
---

# Continuity Guard

Continuity Guard is a lightweight read-only check for important action boundaries. It helps compatible agents re-ground against repo-local AICTX state before edits, risky commands, finalization, final answers, scope changes, agent switches, or continuing after idle/restart.

It does not detect context compaction directly, log reasoning, call external services, mutate continuity state, or return the full resume capsule.

## CLI

```bash
aictx guard --repo . --action edit --paths src/example.py --intent "fix parser edge case" --risk normal --json
```

Supported actions:

```text
before_first_edit edit risky_command finalize final_answer scope_change agent_switch continue_after_idle
```

Options:

```text
--paths <path>      repeatable path involved in the action
--command <command> command involved in the action
--intent <text>     short action intent
--risk low|normal|high
--agent-id <id>
--session-id <id>
--json
```

## MCP

Readonly MCP profile exposes:

```text
aictx_continuity_guard
```

Example input:

```json
{
  "action": "edit",
  "paths": ["src/example.py"],
  "command": "",
  "intent": "fix parser edge case",
  "risk": "normal",
  "agent_id": "codex",
  "session_id": "optional-session-id"
}
```

## Output

The guard returns compact JSON:

```json
{
  "status": "ok",
  "decision": "allow",
  "warnings": [],
  "checks": {
    "work_state": "ok",
    "contract_alignment": "ok",
    "continuity_quality": "ok",
    "lifecycle": "ok",
    "validation": "ok"
  },
  "suggested_next": "continue"
}
```

Decision values:

- `allow`: action appears aligned.
- `caution`: continue, but consider warnings.
- `re_ground`: re-read AICTX state before acting.
- `block`: stop for explicit confirmation; reserved for destructive/high-risk or clearly invalid boundary states.

## Recommended use

Call the guard before important boundaries, not every trivial step:

- first edit
- edit outside known scope
- risky/destructive command
- final answer
- finalize
- explicit scope change
- agent switch
- continuing after idle/restart/possible context loss

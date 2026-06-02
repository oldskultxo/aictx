---
title: "Steer Guard"
description: "Read-only user-intervention classification for active AICTX agent work."
---

# Steer Guard

Steer Guard is a lightweight read-only classifier for user comments that arrive while an agent is already working. It decides whether the message changes the active task, scope, strategy, validation expectations, or should be treated as a side comment.

It complements Continuity Guard:

```text
resume -> work -> user comment -> steer guard -> optional re-ground/update -> continuity guard -> continue/finalize
```

Steer Guard does not mutate Work State, contracts, or validation expectations in V1. It returns compact suggested updates only.

## CLI

```bash
aictx steer --repo . --message "don't touch src/auth.py" --current-action edit --paths src/auth.py --json
```

Options:

```text
--message <text>                         required user message
--current-action edit|command|finalize|final_answer|planning|unknown
--paths <path>                           repeatable path involved in the current action
--agent-id <id>
--session-id <id>
--json
```

`--apply` is reserved for a future explicit mutation mode and is not exposed in V1.

## MCP

Readonly MCP profile exposes:

```text
aictx_steer_guard
```

Example input:

```json
{
  "message": "don't touch src/auth.py",
  "current_action": "edit",
  "paths": ["src/auth.py"],
  "agent_id": "claude",
  "session_id": "optional-session-id"
}
```

## Output

```json
{
  "status": "warning",
  "classification": "scope_constraint",
  "decision": "update_contract",
  "impact": "contract_update_required",
  "summary": "User added a constraint: do not edit src/auth.py.",
  "agent_instruction": "Pause before the next edit and continue without touching src/auth.py.",
  "suggested_updates": {
    "forbidden_paths": ["src/auth.py"],
    "work_state_note": "Avoid src/auth.py unless the user explicitly allows it."
  }
}
```

Classifications include scope changes/constraints, validation changes, strategy changes, new requirements, cancellations, clarifications, side comments, risk warnings, agent corrections, and unknown messages.

If the message is ambiguous, Steer Guard returns `classification=unknown` and `decision=ask_user`.

## AICTX 6.11 agent lifecycle enforcement

AICTX 6.11 adds compact runtime metadata to `aictx resume --json`:

- `runner_contract`: AICTX is required, MCP is preferred, CLI fallback is mandatory, and agents should verify `aictx_resume`, `aictx_finalize`, `aictx_continuity_guard`, and `aictx_steer_guard` once per session.
- `guard_triggers`: stable action boundaries for first edit, scope changes, risky commands, user steering, and final answers.
- `execution_contract.validation_policy`: task-type-aware validation expectations so code tasks require focused evidence while documentation and analysis tasks stay advisory.

Routine agent startup can use `aictx resume --repo . --task "<task goal>" --json --brief` for a smaller payload. Standard mode remains the default for compatibility.

Finalize now captures a compact git-state snapshot when Git is available and persists handoffs with `agent_id`, `adapter_id`, `session_id`, and `evidence_quality`.

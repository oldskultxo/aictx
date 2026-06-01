
# Issue 2 — Add Steer Guard for user-intervention handling during active agent work

## Title

Add Steer Guard for user-intervention handling during active agent work

## Dependency

Depends on:

```text
Issue 1 — Continuity Guard
```

Do not implement Steer Guard before Continuity Guard exists.

Steer Guard should reuse the same design principles and, where possible, the same internal evaluation primitives.

## Summary

Add a **Steer Guard** that classifies user comments made while an agent is already working, and determines whether the comment changes the active task, scope, contract, validation expectations, strategy or Work State.

The goal is to prevent mid-task user comments from being ignored, over-applied, or incorrectly merged into the current task.

## Problem

During active coding-agent work, users often add comments such as:

- "wait, don't touch that file"
- "also update the docs"
- "actually use the simpler approach"
- "don't run the full suite"
- "ignore that, it was just an idea"
- "stop"
- "before continuing, check this other file"
- "this is only a constraint, not a new task"

Agents may handle these poorly:

- ignore the new user instruction
- overreact and abandon the original task
- silently change scope without updating Work State
- continue with an outdated execution contract
- finalize with old validation expectations
- mix side comments with task requirements

## Goal

Implement a lightweight user-intervention classifier and steering output.

Steer Guard should answer:

> Does this new user message change the active task or how the agent should continue?

## Non-goals

- Do not implement a general chat router.
- Do not replace human instruction following.
- Do not rewrite the full conversation.
- Do not summarize every user message.
- Do not mutate Work State automatically in the first version unless explicitly requested by a supported flag.
- Do not create long prompts.
- Do not call external services.
- Do not depend on a specific agent.

## CLI

Add:

```bash
aictx steer --repo . --message "<user message>" --json
```

Supported options:

```bash
--message "<user message>"
--current-action <edit|command|finalize|final_answer|planning|unknown>
--paths <path> [--paths <path> ...]
--agent-id "<agent id>"
--session-id "<session id>"
--apply
--json
```

`--message` is required.

`--apply` is optional and should be disabled by default.

Initial implementation should be read-only unless `--apply` is explicitly used.

If `--apply` is not implemented in the first version, document it as reserved and do not expose it.

## MCP

Add MCP tool:

```text
aictx_steer_guard
```

Initial MCP profile: `readonly`.

If mutation support is added later, it must be a separate explicit mode or require standard/full profile.

## Input schema

MCP input should support:

```json
{
  "message": "don't touch src/auth.py",
  "current_action": "edit",
  "paths": ["src/auth.py"],
  "agent_id": "claude",
  "session_id": "optional-session-id"
}
```

Only `message` is required.

## Output schema

Return compact JSON.

Example scope constraint:

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

Example side comment:

```json
{
  "status": "ok",
  "classification": "side_comment",
  "decision": "continue",
  "impact": "none",
  "summary": "User comment does not change the current task.",
  "agent_instruction": "Continue with the current plan."
}
```

Example validation change:

```json
{
  "status": "warning",
  "classification": "validation_change",
  "decision": "update_validation",
  "impact": "validation_update_required",
  "summary": "User changed validation expectations.",
  "agent_instruction": "Use targeted tests instead of the full suite for this task.",
  "suggested_updates": {
    "validation_note": "Do not run full suite unless later requested."
  }
}
```

Example cancellation:

```json
{
  "status": "warning",
  "classification": "cancellation",
  "decision": "pause",
  "impact": "work_should_pause",
  "summary": "User asked the agent to stop or wait.",
  "agent_instruction": "Stop current work and wait for a new instruction."
}
```

## Classifications

Supported classifications:

```text
scope_change
scope_constraint
priority_change
validation_change
strategy_change
new_requirement
cancellation
clarification
side_comment
risk_warning
agent_correction
unknown
```

## Decisions

Supported decisions:

```text
continue
pause
replan
re_ground
update_contract
update_validation
append_requirement
ignore_as_side_comment
ask_user
```

Meaning:

- `continue`: current work can continue.
- `pause`: stop until further instruction.
- `replan`: task plan should be updated.
- `re_ground`: re-read AICTX state before continuing.
- `update_contract`: execution scope/contract should be updated.
- `update_validation`: validation expectations should change.
- `append_requirement`: add a requirement to the active Work State.
- `ignore_as_side_comment`: comment does not change current work.
- `ask_user`: message is ambiguous and needs clarification.

## Relationship to Continuity Guard

Steer Guard handles **user-intervention boundaries**.

Continuity Guard handles **action boundaries**.

Expected flow:

```text
resume -> work -> user comment arrives -> steer guard -> optional re-ground/update -> action guard -> continue/finalize
```

Steer Guard may recommend calling Continuity Guard after classification.

Example:

```json
{
  "decision": "update_contract",
  "agent_instruction": "Update scope, then call continuity guard before the next edit."
}
```

## Mutation policy

Initial version should be read-only.

It should produce `suggested_updates`, not apply them.

Do not mutate Work State, contracts or validation expectations by default.

Optional future behavior:

```bash
aictx steer --repo . --message "also update docs" --apply --json
```

If `--apply` is implemented, it must:

- write minimal structured updates
- record that the update came from user steering
- preserve original message
- be covered by tests
- never silently overwrite existing Work State

## Token and command cost constraints

Steer Guard must stay lightweight.

Requirements:

- Do not summarize full conversation.
- Do not return full resume capsule.
- Do not return long context.
- Return classification, decision, short summary and compact suggested updates.
- Do not call this for every user message unless there is an active Work State or active agent execution.
- Document recommended usage only when the user interrupts or modifies an active task.

## Heuristic implementation guidance

Initial implementation can be deterministic / rule-based.

Use simple pattern matching for common cases:

- cancellation: "stop", "wait", "pause", "don't continue"
- scope constraint: "don't touch", "avoid", "do not edit"
- validation change: "don't run full suite", "run only", "skip tests"
- new requirement: "also", "add", "include", "update docs"
- strategy change: "simpler", "use another approach", "instead"
- clarification: "I mean", "to clarify", "what I meant"
- risk warning: "be careful", "don't break", "avoid risky"
- agent correction: "that's wrong", "not that", "you misunderstood"

The implementation does not need perfect NLP.

If unsure, return:

```json
{
  "classification": "unknown",
  "decision": "ask_user"
}
```

## Files likely to edit

Likely new files:

```text
src/aictx/steer_guard.py
tests/test_steer_guard.py
docs/STEER_GUARD.md
```

Likely modified files:

```text
src/aictx/cli/__init__.py
src/aictx/mcp/tools.py
src/aictx/mcp/permissions.py
docs/MCP.md
docs/USAGE.md
README.md
CHANGELOG.md
```

Only edit version files if this issue is being implemented as part of a release branch.

## Tests

Add deterministic tests for:

- side comment returns `continue` or `ignore_as_side_comment`.
- "don't touch src/auth.py" returns `scope_constraint` and `update_contract`.
- "also update docs" returns `new_requirement` and `append_requirement`.
- "don't run the full suite" returns `validation_change` and `update_validation`.
- "stop" or "wait" returns `cancellation` and `pause`.
- ambiguous message returns `unknown` and `ask_user`.
- MCP tool `aictx_steer_guard` is available in readonly profile.
- Steer Guard is read-only by default.
- No Work State mutation occurs unless explicit mutation support is implemented.

## Acceptance criteria

- `aictx steer` exists.
- MCP tool `aictx_steer_guard` exists.
- Steer Guard depends conceptually and technically on Continuity Guard.
- Steer Guard is agent-agnostic.
- Steer Guard is read-only by default.
- Steer Guard classifies mid-task user comments.
- Steer Guard returns compact JSON.
- Steer Guard distinguishes side comments from task-changing instructions.
- Steer Guard can recommend `continue`, `pause`, `replan`, `re_ground`, `update_contract`, `update_validation`, `append_requirement`, `ignore_as_side_comment`, or `ask_user`.
- Steer Guard does not increase token usage through long outputs.
- Steer Guard does not call external services.
- Tests cover representative user-intervention cases.
- Docs explain that Continuity Guard protects action boundaries and Steer Guard protects user-intervention boundaries.

## Title

Add Continuity Guard for lightweight action-boundary re-grounding

## Summary

Add a lightweight **Continuity Guard** that agents can call before important action boundaries to check whether the next action is still aligned with repo-local continuity.

The goal is **not** to detect context compaction directly.

The goal is to make important actions re-ground against durable AICTX state before the agent edits, runs risky commands, finalizes, or returns a final answer.

## Problem

Agents can lose or distort context because of:

- session restart
- context compaction
- long-running tasks
- switching between agents
- drift from the original task
- stale or weak continuity artifacts

AICTX already stores Work State, execution contracts, Continuity Quality, lifecycle diagnostics, validation evidence and related continuity artifacts.

However, an agent may continue acting from its current in-context memory without re-checking the durable repo-local state.

This can lead to:

- edits outside expected scope
- final answers without validation
- repeated failed commands
- acting on stale Work State
- ignoring contract gaps
- trusting compacted/truncated context

## Goal

Implement a read-only guard that returns compact steering signals before important actions.

The guard should answer:

> Is this action still aligned with the current repo-local continuity state?

## Non-goals

- Do not implement continuous reasoning logging.
- Do not capture every thought.
- Do not summarize full conversations.
- Do not detect context compaction directly.
- Do not mutate continuity state by default.
- Do not load or return the full resume capsule.
- Do not call external services.
- Do not add a dashboard.
- Do not make the agent call this before every trivial operation.

## CLI

Add:

```bash
aictx guard --repo . --action <action> --json
```

Supported options:

```bash
--action <before_first_edit|edit|risky_command|finalize|final_answer|scope_change|agent_switch|continue_after_idle>
--paths <path> [--paths <path> ...]
--command "<command>"
--intent "<short intent>"
--risk <low|normal|high>
--agent-id "<agent id>"
--session-id "<session id>"
--json
```

`--json` should be supported and should be the primary interface.

Human-readable output may be minimal.

## MCP

Add MCP tool:

```text
aictx_continuity_guard
```

The MCP tool must be available to all compatible agents.

It must be agent-agnostic and not rely on Codex-specific, Claude-specific or Copilot-specific behavior.

Initial MCP profile: `readonly`.

If future guard telemetry is added, telemetry writes must be separate from the read-only guard behavior.

## Input schema

MCP input should support:

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

Only `action` is required.

## Output schema

Return compact JSON.

Example OK:

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

Example caution:

```json
{
  "status": "warning",
  "decision": "caution",
  "warnings": [
    {
      "code": "outside_expected_scope",
      "severity": "warning",
      "message": "Requested edit path is outside current contract scope."
    }
  ],
  "checks": {
    "work_state": "ok",
    "contract_alignment": "warning",
    "continuity_quality": "ok",
    "lifecycle": "ok",
    "validation": "ok"
  },
  "suggested_next": "re-ground before editing outside expected scope"
}
```

Example re-ground:

```json
{
  "status": "warning",
  "decision": "re_ground",
  "warnings": [
    {
      "code": "active_work_state_stale",
      "severity": "warning",
      "message": "Active Work State appears stale."
    },
    {
      "code": "validation_evidence_missing",
      "severity": "warning",
      "message": "Expected validation evidence is missing."
    }
  ],
  "checks": {
    "work_state": "warning",
    "contract_alignment": "ok",
    "continuity_quality": "warning",
    "lifecycle": "warning",
    "validation": "warning"
  },
  "suggested_next": "run resume or prepare before continuing"
}
```

## Decisions

Allowed decision values:

```text
allow
caution
re_ground
block
```

Meaning:

- `allow`: action appears aligned.
- `caution`: action can continue, but warnings should be considered.
- `re_ground`: agent should re-read AICTX state before acting.
- `block`: action should not proceed without user confirmation or explicit re-scope.

`block` should be rare and reserved for destructive/risky commands or clearly invalid finalization/final answer states.

## Checks

Continuity Guard should evaluate at least:

### Work State

- Is there an active Work State?
- Is it stale?
- Does the requested action appear aligned with the active task/next action?
- Is there an open risk or pending next action that should be considered?

### Execution Contract

- Does `action=edit` align with expected edit scope?
- Does `action=before_first_edit` align with expected first action?
- Does `action=finalize` or `action=final_answer` have missing required validation?
- Does the requested path conflict with contract scope?

### Continuity Quality

- Are there stale, missing, demoted, obsolete or unverified continuity warnings?
- Are there deleted/missing file references relevant to the requested paths?
- Is validation evidence missing from carried continuity?

### Lifecycle Diagnostics

- Was resume observed without finalize?
- Is there an active related session?
- Were changes finalized before without commands/tests?
- Is there stale Work State or stale handoff relevant to the task?

### Path / scope alignment

For `action=edit` and `action=scope_change`:

- Compare supplied paths with Work State relevant files.
- Compare supplied paths with execution contract edit scope.
- Use RepoMap/Task Context Pack hints if available.
- Warn on paths clearly outside expected scope.

## Token and command cost constraints

Continuity Guard must stay lightweight.

Requirements:

- Do not return full resume capsule.
- Do not return full loaded context.
- Do not return all decisions/failures/handoffs.
- Return compact warning codes and short messages.
- Prefer machine-readable compact JSON.
- Avoid long prose responses.
- Do not require the agent to call guard before every trivial action.
- Document recommended use only at important action boundaries.

## Recommended guard boundaries

Agents should call guard before:

- first edit
- edit outside known scope
- risky/destructive command
- final answer
- finalize
- explicit scope change
- agent switch
- continuing after idle/restart/possible context loss

Agents should not call guard for every internal reasoning step.

## Files likely to edit

Likely new files:

```text
src/aictx/continuity_guard.py
tests/test_continuity_guard.py
docs/CONTINUITY_GUARD.md
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

- `guard --action before_first_edit` returns `allow` when Work State and contract are aligned.
- `guard --action edit --paths <outside-scope>` returns `caution` or `re_ground`.
- `guard --action final_answer` warns when validation evidence is missing.
- `guard --action finalize` warns when expected validation is missing.
- stale Work State produces `re_ground`.
- Continuity Quality warning is surfaced compactly.
- lifecycle warning is surfaced compactly.
- MCP tool `aictx_continuity_guard` is available in readonly profile.
- MCP tool returns compact JSON.
- guard does not mutate continuity state.

## Acceptance criteria

- `aictx guard` exists.
- MCP tool `aictx_continuity_guard` exists.
- Guard works for all agents; no agent-specific logic is required.
- Guard is read-only by default.
- Guard returns compact JSON.
- Guard does not load/return full resume capsule by default.
- Guard evaluates Work State, execution contract, Continuity Quality and lifecycle diagnostics.
- Guard supports path/scope checks for edit actions.
- Guard can return `allow`, `caution`, `re_ground`, or `block`.
- Guard is documented as an action-boundary re-grounding tool.
- Tests cover ok, caution and re_ground cases.
- No external service calls are introduced.
- Token and command usage remain intentionally bounded.

---

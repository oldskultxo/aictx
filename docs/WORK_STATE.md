---
title: "Work State for Coding-Agent Continuity"
description: "Learn how AICTX Work State preserves suspended active-task context so AI coding agents can resume work across sessions."
---

# Work State

Work State is AICTX’s repo-local artifact for suspended active-task continuity.

It answers:

```text
Where was the active work left?
```

---

## What it preserves

A Work State thread can preserve:

- goal;
- current hypothesis;
- active files;
- verified items;
- unverified assumptions;
- discarded paths;
- compact discarded hypotheses / abandoned approaches;
- next action;
- recommended commands;
- risks;
- uncertainties;
- source execution ids;
- compact `contract_gaps` and strongest carried gap metadata when unresolved contract gaps exist.

---

## What it is not

Work State is not a task manager, kanban board, issue tracker, planner, or hidden semantic memory.

It is deterministic operational continuity.

---

## Dead-end capture

Work State can preserve compact discarded hypotheses when an agent explicitly records that it abandoned an approach.

Example:

```json
{
  "summary": "Local diff was not the cause of the deploy failure.",
  "reason": "User clarified the failure came from CI/deploy.",
  "confidence": "medium"
}
```

This is not chain-of-thought. It is an operational breadcrumb for future sessions.

---

## Artifacts

```text
.aictx/tasks/active.json
.aictx/tasks/threads/<task-id>.json
.aictx/tasks/threads/<task-id>.events.jsonl
```

Only one active pointer exists per repo. Old threads remain stored.

---

## Public CLI

```bash
aictx task start "Fix login token refresh" --json
aictx task status --json
aictx task update --json-patch '{"next_action":"run targeted auth tests"}' --json
aictx task list --json
aictx task show fix-login-token-refresh --json
aictx task resume fix-login-token-refresh --json
aictx task close --status resolved --json
```

These commands are available for inspection and advanced control. In normal supported-agent workflows, the agent may update Work State through runtime integration.

---

## Runtime integration

`prepare_execution()` loads active Work State when safe and exposes compact `active_work_state`.

`finalize_execution()` can update Work State from factual evidence or explicit payloads.

Automatic updates stay conservative.

Unresolved contract compliance gaps can also carry over into Work State after finalize. AICTX reuses existing Work State fields and may also preserve compact structured gap metadata:

```text
unverified
risks
recommended_commands
next_action
source_execution_ids
contract_gaps
strongest_contract_gap
```

Contract gap severities are guidance, not deterministic enforcement. Initial mapping is `missing_validation -> needs-validation`, `edit_outside_scope -> needs-review`, `missing_first_action -> caution`, and `structural_entrypoints_ignored -> caution`; none are hard-blocking by default.

For example, a successful execution that did not observe the canonical validation command can be saved as `status: paused` with `next_action: run expected validation command` and a `needs-validation` carryover gap. The next `resume` should surface that carryover before completed handoffs.

---

## Branch-safe loading

AICTX stores:

- branch;
- HEAD;
- dirty flag;
- changed files;
- captured timestamp.

Rules:

| Situation | Behavior |
|---|---|
| same branch | load |
| same branch, changed HEAD | load with warning |
| different branch, saved commit reachable from current HEAD | load with warning |
| different branch, saved commit not reachable | skip |
| saved state dirty and branch changed | skip |
| old Work State/no git | load conservatively |

Skipped Work State is not deleted.

---

## Relationship to other layers

```text
Work State = current suspended task state.
Handoff = latest operational summary.
Strategy Memory = what worked.
Failure Memory = what failed.
RepoMap = where to look.
```

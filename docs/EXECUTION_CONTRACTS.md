---
title: "Execution Contracts for Coding-Agent Continuity"
description: "Understand AICTX execution contracts, compliance records, and how coding agents preserve observable continuity across sessions."
---

# Execution Contracts and Compliance

AICTX v6 keeps a compact contract loop around the normal agent lifecycle, with persisted contract records and evaluated-only reporting.

```text
resume -> execution_contract -> observed execution -> finalize compliance -> metrics -> next resume signal
```

This is an audit and continuity mechanism. It is not a sandbox, not a blocker, and not an autonomous repair system.

---

## What the resume contract is

At normal task startup, supported agents should run:

```bash
aictx resume --repo . --task "<task goal>" --json
```

`--task` should contain only the work goal. It should exclude reporting instructions, metrics schemas, output format rules, benchmark text, logging instructions, and meta-instructions about the final answer.

The resume payload may include an `execution_contract` with fields such as:

- `task_goal`;
- `first_action`;
- `first_action_policy`;
- `edit_scope`;
- `test_command`;
- `finalize_command`;
- `contract_strength`.

The contract tells the agent where to start, what scope to edit, which validation command to prefer, and how to close the lifecycle.

---

## Contract strength

Contract strength is a guidance signal, not a runtime enforcement mechanism.

Typical meanings:

- `strict`: binding operational route; follow first action, edit scope, and canonical validation unless contradicted by the repo.
- `soft`: guided route with fallback; prefer the contract, but allow narrow task-driven discovery when necessary.
- `exploratory`: guardrails plus minimal task-driven discovery; avoid broad repo orientation.

---

## What compliance auditing does

`finalize_execution()` can evaluate observed execution against the latest compatible resume contract.

It uses observable signals such as:

- `files_opened`;
- `files_edited`;
- `commands_executed`;
- `tests_executed`;
- `notable_errors`;
- `error_events`.

The compact result can be:

```text
Contract: followed.
Contract: partial — canonical test was not observed.
Contract: violated — edited outside contract scope.
Contract: not evaluated — no matching resume contract.
Contract: not evaluated — no execution observation.
```

---

## Where compliance appears

Detailed rows are persisted in:

```text
.aictx/metrics/contract_compliance.jsonl
```

The compact user-facing line appears in:

```text
finalize_execution().agent_summary_text
```

Historical aggregates are available through:

```bash
aictx report real-usage
```

The next resume can include a compact previous-contract signal, for example:

```text
Previous contract: followed.
```

The default resume should not include verbose audit evidence.

In v6.3, unresolved contract gaps can also become Work State carryover. The minimum gap types are:

- `missing_validation`
- `missing_first_action`
- `edit_outside_scope`
- `structural_entrypoints_ignored`

Each gap carries compact guidance metadata: `severity`, `policy`, and `blocking`. Initial severities are conservative:

| Gap kind | Severity | Policy | Blocking by default |
|---|---|---|---|
| `missing_validation` | `needs-validation` | `prioritize_before_new_work` | no |
| `edit_outside_scope` | `needs-review` | `surface_before_continuing` | no |
| `missing_first_action` | `caution` | `surface_before_continuing` | no |
| `structural_entrypoints_ignored` | `caution` | `surface_as_context` | no |

`blocking` exists as a possible severity, but current gap carryover does not hard-block by default. Severity is guidance from observable execution evidence, not proof of correctness.

Gaps are saved through existing Work State fields such as `unverified`, `risks`, `recommended_commands`, `next_action`, and `source_execution_ids`, and may also be preserved in a compact structured `contract_gaps` field. This means a successful execution with pending validation can pause the Work State for the next `resume` instead of being hidden behind a completed handoff. If multiple gaps are present, the strongest severity is surfaced in Work State / resume guidance.

---

## What compliance does not do

Contract compliance does not:

- add another normal agent command;
- block file edits or command execution;
- guarantee correctness;
- prove productivity, speed, or token savings;
- infer facts that were not observed;
- inspect hidden agent reasoning;
- know exact command order unless ordered trace data exists.

If no compatible contract exists, compliance is `not_evaluated — no matching resume contract`.

If a contract exists but no observable execution signals are available, compliance is `not_evaluated — no execution observation`.

If orientation-like commands are observed but no ordered trace exists, AICTX should treat that conservatively as an order-unknown warning, not as a hard proof of broad pre-edit exploration.

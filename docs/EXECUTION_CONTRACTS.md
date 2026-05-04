# Execution Contracts and Compliance

AICTX v5.3 adds a compact contract loop around the normal agent lifecycle.

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

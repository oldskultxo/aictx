# Handoffs and Decisions

Handoffs and Decisions preserve explicit continuity between executions.

They answer:

```text
What did the previous session leave behind?
What decisions should the next session not rediscover?
```

---

## Core idea

AICTX separates several kinds of continuity:

```text
Work State = current suspended task state.
Handoff = how the previous execution ended.
Decision = explicit project/architecture fact.
Semantic repo memory = compact repo-level continuity context.
Execution Summary = factual latest finalize output.
Resume capsule = compiled agent-facing startup brief.
```

Handoffs are historical continuity. Work State is live operational continuity.
The resume capsule selects across these sources so agents do not need to inspect
the raw artifacts at normal startup.

---

## Artifacts

Primary artifacts:

```text
.aictx/continuity/handoff.json
.aictx/continuity/handoffs.jsonl
.aictx/continuity/decisions.jsonl
.aictx/continuity/semantic_repo.json
```

Related continuity artifacts:

```text
.aictx/continuity/staleness.json
.aictx/continuity/dedupe_report.json
.aictx/continuity/continuity_metrics.json
.aictx/continuity/last_execution_summary.md
.aictx/continuity/resume_capsule.md
.aictx/continuity/resume_capsule.json
```

`resume_capsule.*` files are generated trace artifacts. They are useful for
debugging and repeatability, but they are local runtime output rather than
durable portable continuity.

---

## `handoff.json`

`handoff.json` stores the latest compact handoff.

It can include:

- summary;
- recommended starting points;
- source execution id;
- update timestamp;
- relevant files or areas;
- next-session hints.

It is useful when there is one latest state the next session should know.

---

## `handoffs.jsonl`

`handoffs.jsonl` stores recent handoff history.

It can preserve a sequence of previous execution endings, including:

- execution id;
- timestamp;
- summary;
- status;
- task type;
- completed items;
- next steps;
- blocked items;
- risks;
- recommended starting points;
- observed files/tests.

Startup continuity can use this history to render a compact “previous session” message.

Example startup shape:

```text
codex@aictx · session #40 · awake

Resuming: branch-safe Work State finalize behavior.
Last progress: finalize behavior aligned with tests.
Next: tests/test_work_state_runtime.py
```

---

## `decisions.jsonl`

`decisions.jsonl` stores explicit project or architecture decisions.

Examples:

```text
Use branch-safe Work State loading, not branch-specific task folders.
Keep RepoMap optional.
Treat Work State as suspended task state, not a task manager.
```

Decisions should be explicit and factual. They should not be inferred from vague execution signals.

---

## `semantic_repo.json`

`semantic_repo.json` can hold compact repo-level continuity facts.

It is useful for broad context that should survive between sessions but does not belong to one active Work State.

---

## Handoffs vs Execution Summary

Execution Summary is the factual output of a finalized execution.

Handoff is continuity derived from execution that the next session can reuse.

The distinction:

```text
Execution Summary = what happened this run.
Handoff = what should be remembered from this run.
```

Both must remain factual.

In final execution summaries, `Next:` means real pending work. `Entry point:`
means a technical resume location such as handoff `recommended_starting_points`.

---

## Handoffs vs Work State

Work State has priority when present because it represents live unfinished work.

Example:

```text
Handoff: docs were improved in previous session.
Work State: currently updating installation guide.
```

The next agent should continue from Work State first, while using handoff for context.

---

## Startup continuity

Startup banner rendering can combine:

- session identity;
- handoff history;
- recommended starting points;
- active Work State;
- next action;
- language preference.

Example:

```text
claude@aictx · session #41 · awake

Resuming: documentation UX.
Last progress: documentation UX updated.
Active task: Public release docs. Next: clarify agent-driven workflow.
```

---

## Staleness and dedupe

AICTX may maintain supporting continuity artifacts:

```text
staleness.json
dedupe_report.json
continuity_metrics.json
```

These help keep continuity useful and bounded.

They do not turn handoffs into hidden memory or semantic proof.

---

## Agent behavior

Agents should use handoffs as compact prior-session context.

Good usage:

```text
The previous session left these starting points. Inspect them before broad discovery.
```

Bad usage:

```text
Assume the handoff proves the feature is correct.
```

---

## Limits

- Handoffs are summaries, not full transcripts.
- Decisions should be explicit, not inferred.
- Handoff history is bounded.
- Staleness can reduce usefulness.
- Handoffs should not override active Work State.
- Missing facts should remain missing.

---

## Related docs

- [Technical overview](TECHNICAL_OVERVIEW.md)
- [Work State](WORK_STATE.md)
- [Execution Summary](EXECUTION_SUMMARY.md)
- [Limitations](LIMITATIONS.md)

# Strategy Memory

Strategy Memory stores successful execution patterns that may be reused in similar future tasks.

It answers:

```text
What worked before in this repo?
```

It is not a planner, task runner, or autonomous decision system. It is repo-local memory of observed successful work.

---

## Artifact

```text
.aictx/strategy_memory/strategies.jsonl
```

Each row is an inspectable record of a previously successful execution pattern.

---

## What it can store

A strategy record may include:

- task type;
- task id or execution id;
- files used;
- entry points;
- commands executed;
- tests executed;
- related errors/signals;
- area id;
- result summary;
- recency;
- similarity/reuse metadata.

The exact fields may evolve, but the purpose is stable:

```text
preserve useful successful execution patterns
```

---

## How it is created

Strategy Memory is updated during `finalize_execution()` when an execution provides enough useful evidence.

Good candidates include executions with:

- observed files;
- successful commands or tests;
- meaningful result summary;
- useful task type or area;
- clear entry points.

AICTX should not store empty or noisy executions as useful strategies.

---

## How it is used

Strategy Memory can be used in three places.

### During prepare

`prepare_execution()` may select a related prior successful strategy and include it in the prepared continuity context.

### Through `aictx suggest`

```bash
aictx suggest --request "fix startup banner" --json
```

This can return suggested entry points, files, related commands/tests, and why a strategy matched.

### Through `aictx reuse`

```bash
aictx reuse --request "fix startup banner" --json
```

This exposes a reusable successful strategy when one is available.

---

## Selection signals

Strategy selection can consider:

- task type;
- request text;
- file overlap;
- primary entry point;
- related commands;
- related tests;
- related errors;
- area id;
- recency;
- similarity breakdown.

The result is a hint, not an instruction.

---

## Strategy Memory vs Failure Memory

```text
Strategy Memory = what worked before.
Failure Memory = what failed before.
```

This distinction is important.

A failed execution may be valuable, but it should not become a positive strategy hint. Failed paths belong in Failure Memory and debugging context.

---

## Strategy Memory vs Work State

```text
Work State = current suspended task state.
Strategy Memory = reusable successful historical pattern.
```

If active Work State exists, it usually matters more than a historical strategy because it represents live unfinished work.

---

## Agent behavior

Agents should treat Strategy Memory as guidance.

Good usage:

```text
A prior successful strategy touched these files and ran these tests. Start there if relevant.
```

Bad usage:

```text
Repeat the previous strategy blindly.
```

---

## Limits

- Strategy reuse is heuristic.
- Matching is based on available signals.
- A selected strategy may be stale.
- A strategy is not proof that the same approach will work again.
- Missing files or changed architecture can reduce usefulness.
- Failed strategies are not reused as positive hints.

---

## Related docs

- [Technical overview](TECHNICAL_OVERVIEW.md)
- [Failure Memory](FAILURE_MEMORY.md)
- [Work State](WORK_STATE.md)
- [Usage](USAGE.md)

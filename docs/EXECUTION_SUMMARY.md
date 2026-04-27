# Execution Summary

AICTX finalization returns a deterministic summary for the coding agent.

---

## Outputs

`finalize_execution()` returns:

- `agent_summary`;
- `agent_summary_text`.

The latest detailed summary may also be written to:

```text
.aictx/continuity/last_execution_summary.md
```

If finalize output is unavailable, agents should say:

```text
AICTX summary unavailable
```

---

## Recommended shape

```text
AICTX summary

Captured:
- command: pytest -q

Updated:
- Work State: next action preserved

Learned:
- no new failure pattern

Next:
- continue from src/aictx/work_state.py
```

---

## Rules

The summary must be factual, compact, useful for the next session, clear about Work State/failure memory changes, and free of unsupported productivity claims.

Do not invent missing data.

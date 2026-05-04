# Execution Summary

AICTX finalization returns a deterministic summary for the coding agent.
`agent_summary_text` is the compact user-facing surface. `last_execution_summary.md` is the detailed diagnostic surface.

The summary source is the finalize lifecycle. `aictx resume` can compile and display prior continuity, but it does not produce the final AICTX summary and does not replace `finalize_execution()`.

---

## Outputs

`finalize_execution()` returns:

- `agent_summary`;
- `agent_summary_text`.

The latest detailed summary may also be written to:

```text
.aictx/continuity/last_execution_summary.md
```

Contract compliance details may be persisted to:

```text
.aictx/metrics/contract_compliance.jsonl
```

If finalize output is unavailable, agents should say:

```text
AICTX summary unavailable
```

---

When `.aictx/continuity/last_execution_summary.md` is generated, the user-facing summary should keep the final details line as a clickable Markdown link:

```text
Details: [last_execution_summary.md](.aictx/continuity/last_execution_summary.md)
```

## Recommended shape

```text
AICTX summary

Context: reused previous strategy + loaded handoff/decisions/preferences.
Map: RepoMap quick ok.
Saved: updated handoff.
Contract: followed.
Entry point: src/aictx/continuity.py, src/aictx/middleware.py.
Details: [last_execution_summary.md](.aictx/continuity/last_execution_summary.md)
```

With real pending work:

```text
AICTX summary

Context: loaded handoff/preferences.
Saved: updated Work State.
Contract: partial — canonical test was not observed.
Next: update docs examples for summary output.
Details: [last_execution_summary.md](.aictx/continuity/last_execution_summary.md)
```

---

## Contract compliance line

When a compatible resume execution contract was available and finalize receives observable execution evidence, the summary may include a compact contract line:

```text
Contract: followed.
Contract: partial — canonical test was not observed.
Contract: violated — edited outside contract scope.
```

If compliance cannot be evaluated, the summary may say:

```text
Contract: not evaluated — no matching resume contract.
Contract: not evaluated — no execution observation.
```

This line is compact and user-facing. Detailed audit evidence belongs in:

```text
.aictx/metrics/contract_compliance.jsonl
aictx report real-usage
```

---

## Rules

The summary must be factual, compact, useful for the next session, clear about Work State/failure memory changes, and free of unsupported productivity claims.

Do not invent missing data.

Do not show low-signal diagnostic internals such as `unknown` task type/area in `agent_summary_text`; keep those details in `last_execution_summary.md`.

Use `Next:` only for real pending work such as `next_steps`, `open_items`, `blocked`, or active Work State `next_action`.

Use `Entry point:` for technical resume locations such as `recommended_starting_points`.

Use `Contract:` only as a compact status line. Do not include verbose violations, evidence lists, or raw JSON in `agent_summary_text`.

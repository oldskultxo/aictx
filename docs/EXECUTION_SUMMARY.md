# Execution Summary

AICTX finalization returns a deterministic summary for the coding agent.
`agent_summary_text` is the compact user-facing surface. `last_execution_summary.md`
is the detailed diagnostic surface.

The summary source is the finalize lifecycle. `aictx resume` can compile and
display prior continuity, but it does not produce the final AICTX summary and
does not replace `finalize_execution()`.

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

When `.aictx/continuity/last_execution_summary.md` is generated, the user-facing
summary should keep the final details line as a clickable Markdown link:

```text
Details: [last_execution_summary.md](.aictx/continuity/last_execution_summary.md)
```

## Recommended shape

```text
AICTX summary

Context: reused previous strategy + loaded handoff/decisions/preferences.
Map: RepoMap quick ok.
Saved: updated handoff.
Entry point: src/aictx/continuity.py, src/aictx/middleware.py.
Details: [last_execution_summary.md](.aictx/continuity/last_execution_summary.md)
```

With real pending work:

```text
AICTX summary

Context: loaded handoff/preferences.
Saved: updated Work State.
Next: update docs examples for summary output.
Details: [last_execution_summary.md](.aictx/continuity/last_execution_summary.md)
```

---

## Rules

The summary must be factual, compact, useful for the next session, clear about
Work State/failure memory changes, and free of unsupported productivity claims.

Do not invent missing data.

Do not show low-signal diagnostic internals such as `unknown` task type/area in
`agent_summary_text`; keep those details in `last_execution_summary.md`.

Use `Next:` only for real pending work such as `next_steps`, `open_items`,
`blocked`, or active Work State `next_action`.

Use `Entry point:` for technical resume locations such as
`recommended_starting_points`.

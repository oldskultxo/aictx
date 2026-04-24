# Execution summary

AICTX finalize output includes a deterministic user-facing summary payload:

- `agent_summary`: structured fields for runner integration
- `agent_summary_text`: compact Markdown that agents must append verbatim to the final user response after finalize

If finalize output is unavailable, agents must say:

```text
AICTX summary unavailable
```

The summary reports only observed or persisted facts:

- whether a prior strategy was reused
- why it was selected when available
- whether learning, strategy memory, or failure memory was stored
- observed file/reopen counts
- commands and tests captured when available

AICTX does not claim quality or speed improvements from this summary.

The summary belongs to the current `4.0.0` continuity runtime contract:

- it is generated after repo-local continuity persistence
- it reports continuity reuse and stored artifacts from the current execution
- it is conservative: it reports observed/persisted facts, not estimated productivity gains
- it may be paired with a startup banner that is shown once per visible session when the runtime indicates it

Related continuity artifacts that may be reflected indirectly in the summary:

```text
.aictx/continuity/handoff.json
.aictx/continuity/decisions.jsonl
.aictx/continuity/semantic_repo.json
.aictx/continuity/staleness.json
.aictx/continuity/continuity_metrics.json
```

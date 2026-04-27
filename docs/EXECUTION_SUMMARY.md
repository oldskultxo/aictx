# Execution summary

`finalize_execution()` returns a deterministic user-facing summary payload:

- `agent_summary`: structured facts for integrations
- `agent_summary_text`: compact summary for the final user response

Current behavior:

- `agent_summary_text` stays compact for chat readability
- a detailed deterministic summary is also written to:

```text
.aictx/continuity/last_execution_summary.md
```

- compact summaries should reference that file with a clickable Markdown link when the surface supports it
- if finalize output is unavailable, agents must say exactly:

```text
AICTX summary unavailable
```

The summary reports only observed or persisted facts, for example:

- reused strategy and selection reason
- loaded continuity value sources when relevant
- stored artifacts such as handoff, decision, strategy, or validated learning
- observed files/tests counts
- next focus when continuity has one
- work state update when finalize preserved an active task thread
- prepared/final/effective task and area classification when that adds real value
- failure memory events when relevant: learned new pattern, recognized repeated pattern, resolved prior failure, or considered prior context

For failure memory, compact summaries include human-readable descriptors when available, for example `typescript typecheck TS2322`, plus the failure id where useful. AICTX should not claim that a failure was avoided unless the execution facts support that wording.

The detailed file may also include:

- prepared/final/effective task type
- prepared/final/effective area
- RepoMap status used during prepare
- active Work State context used during prepare
- which Work State fields were updated during finalize
- AICTX value sources
- next-session guidance

Additional optional runtime outputs may appear:

- `.aictx/repo_map/config.json`
- `.aictx/repo_map/manifest.json`
- `.aictx/repo_map/index.json`
- `.aictx/repo_map/status.json`

Important contract detail:

- agents should use `agent_summary_text` as the canonical factual source
- agents may localize or lightly humanize the final rendering when policy allows
- agents must preserve real facts and must not invent missing data

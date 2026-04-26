# Limitations

- file and error tracking still depend on explicit input from the agent/runner or wrapped execution capture
- task typing is deterministic and evidence-based, but still heuristic rather than semantic understanding
- `prepare` classification is provisional; `finalize` can correct it with observed files/tests/commands/errors
- even with observed reclassification, mixed implementation+validation work can still be borderline between `feature_work`, `refactoring`, and `testing`
- continuity quality depends on runner support and agent cooperation with prepare/finalize
- strategy reuse is deterministic and conservative; task type, prompt similarity, file overlap, entry point, commands/tests/errors, area, and recency can influence selection
- handoff history (`.aictx/continuity/handoffs.jsonl`) is intentionally bounded; it is continuity aid, not full audit history
- packet/context generation is conservative and task-dependent; it does not run for every execution
- RepoMap depends on optional Tree-sitter support; if unavailable, RepoMap stays disabled/unavailable
- RepoMap quick refresh is budgeted and can preserve last-known structural state when refresh is partial
- continuity metrics are aggregate observed counts, not proof of productivity gain
- `reflect` is a small deterministic rule set over recent logs; it is guidance, not diagnosis
- missing data stays empty or `unknown`; AICTX does not invent runtime evidence or claim failure avoidance without supporting execution facts
- `.aictx/continuity/last_execution_summary.md` tracks only the latest finalized execution and is overwritten on each run
- parser coverage is broad but not exhaustive; unknown toolchain outputs fall back to generic structured failure events
- AICTX is safe for evaluation and cautious repo-local workflows; it is not a guarantee of better speed, quality, or exploration

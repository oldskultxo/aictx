# Limitations

- file tracking depends on explicit input from the agent or runtime
- task typing is deterministic but shallow: explicit runner metadata wins; otherwise AICTX uses keyword/path hints and falls back to `unknown`
- strategy reuse is heuristic and conservative; task type, prompt similarity, file overlap, primary entry point, command/test/error similarity, and area can influence selection, with recency as a secondary signal
- continuity artifacts are only as good as the real signals the runner and agent provide; missing prepare/finalize cooperation weakens handoff, decision, semantic, and metrics quality
- middleware context packet generation is conservative and task-dependent; it does not run for every execution and still depends on the runtime path actually calling `prepare_execution`
- there is no guaranteed improvement in speed, quality, or file exploration
- the system depends on runner support and agent cooperation to call the runtime, use guidance, and include the required final AICTX summary
- failed strategies are stored, and failure memory can provide avoidance context, but this is still deterministic and limited rather than rich semantic diagnosis
- stale memory handling is conservative and may exclude clearly stale startup artifacts; it does not automatically repair missing paths or obsolete repo knowledge
- continuity metrics are aggregate counts of observed events, not proof of productivity gain
- `reflect` uses only the latest execution log and a small deterministic rule set; it is guidance, not diagnosis
- automatic capture is best-effort and runner-dependent; missing data stays empty or null and is not invented
- public operational command outputs are deterministic JSON; internal wrapped execution may print command output plus the AICTX summary, and usefulness still depends on real stored execution data
- current releases are safe for evaluation and cautious repo-local use, not a strong automation contract for broad team-wide rollout
- `aictx uninstall` cleans registered repositories and AICTX global state; repositories unknown to AICTX are not auto-discovered

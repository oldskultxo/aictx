# Limitations

- file tracking depends on explicit input from the agent or runtime
- task typing is deterministic but shallow: explicit runner metadata wins; otherwise AICTX uses keyword/path hints and falls back to `unknown`
- strategy reuse is heuristic and conservative; file overlap and primary entry point matches are preferred, with recency as a secondary signal
- middleware context packet generation is disabled in the default execution path; packet helpers remain available for explicit/internal use only
- there is no guaranteed improvement in speed, quality, or file exploration
- the system depends on agent cooperation to call the runtime and use guidance
- failed strategies are stored, but they are not yet used for negative guidance beyond exclusion from reuse
- `reflect` uses only the latest execution log and a very small rule set
- missing data stays empty or null; it is not invented
- command outputs are deterministic JSON, but their usefulness still depends on the quality of real stored execution data
- current releases are safe for evaluation and cautious repo-local use, not a strong automation contract for broad team-wide rollout
- `aictx uninstall` cleans registered repositories and AICTX global state; repositories unknown to AICTX are not auto-discovered

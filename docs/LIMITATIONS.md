# Limitations

## Current limits

- file tracking depends on explicit input from the agent or runtime
- there is no ranking of strategies
- there is no guaranteed improvement in speed, quality, or file exploration
- the system depends on agent cooperation to call the runtime and use guidance
- failed strategies are stored, but they are not yet used for negative guidance beyond exclusion from reuse
- `reflect` uses only the latest execution log and a very small rule set
- missing data stays empty or null; it is not inferred

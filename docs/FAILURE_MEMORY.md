# Failure memory

AICTX records failed executions as repo-local, inspectable failure patterns under:

- `.aictx/failure_memory/failure_patterns.jsonl`
- `.aictx/failure_memory/failure_index.json`

Records include deterministic fields such as:

- failure signature
- task type
- area id
- error text
- failed command
- involved files
- attempted fix summary
- status / resolution link

Current behavior:

- failed strategies are stored for history and debugging
- they are not reused as positive strategy hints
- related failure context can still be loaded for avoidance/debugging
- successful later executions can resolve matching open failure records

As with task/area typing elsewhere in AICTX, the stored failure task/area values now come from the effective observed classification when available.

# Failure memory

AICTX records failed executions as repo-local, inspectable failure patterns under:

- `.aictx/failure_memory/failure_patterns.jsonl`
- `.aictx/failure_memory/failure_index.json`

Records include a deterministic signature, task type, area, error text, failed command, involved files, attempted summary, status, and optional resolution link.

Failure records are not reused as positive strategy hints. They are exposed as related debugging context and can be linked to later successful executions when the same task/file/area signals recur.

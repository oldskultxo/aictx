# Failure memory

AICTX records failed executions as repo-local, inspectable failure patterns under:

- `.aictx/failure_memory/failure_patterns.jsonl`
- `.aictx/failure_memory/failure_index.json`

## What is captured

AICTX 4.4 can capture command, test, lint, typecheck, build, and compilation failures as structured `error_events` when the runtime observes command output or receives explicit event JSON.

Each event is compact and deterministic:

```text
toolchain, phase, severity, message, code, file, line, command, exit_code, fingerprint
```

`notable_errors` remains part of the contract as a compact list of strings. When structured events exist, AICTX derives useful notable errors from them for backward compatibility.

Current toolchain recognition includes:

- Python: traceback/pytest-style failures, mypy, ruff, pyright
- JavaScript/TypeScript: npm, tsc `TSxxxx`, ESLint, Jest/Vitest-style output
- Go, Rust/Cargo, Java/JVM/Maven, .NET, C/C++, Ruby, PHP
- generic fallback for unknown failed commands

## Failure records

Records include deterministic fields such as:

- failure signature / fingerprint
- task type
- area id
- error text and symptoms
- structured `error_events` when available
- toolchains, phases, error codes, and error fingerprints
- failed command and ineffective commands
- involved/related files
- attempted fix summary
- occurrence count
- status / resolution link

## Reuse and avoidance

Current behavior:

- failed strategies are stored for history and debugging
- they are not reused as positive strategy hints
- related failure context can still be loaded during prepare for avoidance/debugging
- lookup ranks failures by task type, area, request text, paths, toolchain, phase, code, fingerprint, and symptoms
- successful later executions can resolve matching open failure records

`agent_summary_text` reports failure memory without inventing causality:

- new failed pattern -> learned a new failure pattern, with a human descriptor such as `typescript typecheck TS2322`
- repeated failed pattern -> recognized an existing failure pattern and updated its occurrence count
- successful related fix -> resolved a prior failure, with descriptor and failure id when available
- prior context loaded without a new failure -> reports that related failure context was considered or used without claiming proof of prevention

As with task/area typing elsewhere in AICTX, stored failure task/area values come from the effective observed classification when available.

# Failure Memory

Failure Memory stores observed failure patterns as repo-local, inspectable data.

---

## Artifacts

```text
.aictx/failure_memory/failure_patterns.jsonl
.aictx/failure_memory/failure_index.json
```

---

## What is captured

AICTX can capture command, test, lint, typecheck, build, and compilation failures when the runtime observes command output or receives explicit error event JSON.

Structured fields can include:

```text
toolchain, phase, severity, message, code, file, line, command, exit_code, fingerprint
```

---

## Reuse semantics

Failure Memory can help later sessions recognize prior failure context.

Failed strategies are not reused as positive strategy hints.

---

## Summary wording

Allowed:

```text
Learned new failure pattern: typescript typecheck TS2322.
Recognized repeated failure pattern: pytest assertion failure.
Resolved prior failure: rust cargo compile E0308.
Related failure context was loaded.
```

Avoid unsupported causal claims such as “AICTX prevented the failure”.

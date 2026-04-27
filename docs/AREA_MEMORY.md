# Area Memory

Area Memory is an advanced continuity signal that groups observed execution facts by repository area.

It is secondary to Work State, Failure Memory, and RepoMap, but can improve context selection.

---

## Area derivation

Examples:

```text
src/aictx/middleware.py -> src/aictx
tests/test_smoke.py -> tests/test_smoke.py
docs/USAGE.md -> docs/USAGE.md
no observed paths -> unknown
```

---

## Artifact

```text
.aictx/area_memory/areas.json
```

---

## Use

Area Memory can influence continuity context, strategy selection, failure lookup, and report visibility.

It is a deterministic hint, not semantic understanding.

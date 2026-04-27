# Upgrade guide

## Current line: 4.5.x

Current documented runtime: `4.5.3`.

For users already on recent `4.x`, there is no special manual migration command. Re-run normal setup when needed:

```bash
aictx install
aictx init
```

---

## 4.5.x

Added:

- Work State under `.aictx/tasks/`;
- public `aictx task start|status|list|show|update|resume|close`;
- active Work State loading in prepare/startup/`aictx next`;
- conservative finalize updates;
- branch-safe Work State loading using git branch/head context;
- skip behavior for unsafe branch mismatch.

No manual migration is expected.

---

## Safe upgrade checklist

```bash
python -m pip install --upgrade aictx
aictx install
aictx init
aictx next
aictx report real-usage
```

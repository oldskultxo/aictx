# Upgrade guide

## Current line: 4.6.x

Current documented runtime: `4.6.0`.

For users already on recent `4.x`, there is no special manual migration command. Re-run normal setup when needed:

```bash
aictx install
aictx init
```

---
## 4.6.x

Added:
- Opt-in git-portable continuity using an AICTX-managed `.gitignore` block and `.aictx/continuity/portability.json` without duplicating canonical artifacts.

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

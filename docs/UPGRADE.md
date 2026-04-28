# Upgrade guide

## Current line: 4.7.x

Current documented runtime: `4.7.0`.

For users already on recent `4.x`, there is no special manual migration command. Re-run normal setup when needed:

```bash
aictx install
aictx init
```

---
## 4.7.x

Added:
- Added `aictx messages mute`.
- Added `aictx messages unmute`.
- Added `aictx messages status`.
- Added `aictx -v`, `aictx --version`.
- Polish startup banner text
- Polish summary output text
- Hardened output messages translations policy
- Docs update

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

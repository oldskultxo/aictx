# Upgrade guide

## Current line: 4.7.x

Current documented runtime: `4.7.1`.

For users already on recent `4.x`, there is no special manual migration command. Re-run normal setup when needed:

```bash
aictx install
aictx init
```

---
## 4.7.x

Added:
- Added repo-local user-facing message controls with `aictx messages mute`, `aictx messages unmute`, and `aictx messages status`.
- Added `aictx -v` and `aictx --version`.
- Added docs coverage for the new message controls and version-check flows in installation, quickstart, usage, and release guidance.

Changed:
- Polished startup banner text and later-session continuity messaging.
- Updated startup banner rendering semantics so runners prefer structured render payloads when the runtime policy points to them.
- Polished final summary output and aligned the execution-summary docs with the current runtime behavior.
- Hardened AICTX user-visible text localization/translation policy so localized output preserves exact facts and technical tokens.

Fixed:
- Restored compatibility for legacy `task` and `agent` aliases in execution middleware flows.
- Introduce a new runtime_compact module to plan and perform compaction of repo runtime artifacts.

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

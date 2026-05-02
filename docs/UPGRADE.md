# Upgrade guide

## Current line: 5.0.x

Current documented runtime: `5.1.0`.

For users already on recent `4.x`, there is no special data migration command. Re-run normal setup so generated runner instructions pick up the v5 startup contract:

```bash
aictx install
aictx init
```

---
## 5.0.x


Changed:
- Implemented self-contained resume capsule first_action, startup guard, anti-runtime startup rule, task-biased entry ranking, and regression tests.

Fixed:
- Replaced parser/CLI-specific resume bias with generic task profile + request-term matching.
- Added path categories/penalties for runtime/generated/metrics/docs/config/source/tests.
- Kept .aictx/** excluded from action targets.
- Allows docs/config/metrics to win only for matching task intent.

Compatibility notes:
- No manual continuity data migration is expected.
- Re-run `aictx install` and `aictx init` after upgrading so managed `AGENTS.md`, `CLAUDE.md`, Codex, and Claude integration text is refreshed.
- Integrations that parsed top-level help to discover `suggest`, `reuse`, `next`, `task`, `messages`, `map`, `report`, `reflect`, or `internal` should use `aictx advanced` or call those commands directly.
- `resume_capsule.*` files are generated local runtime output; do not treat them as durable portable continuity.

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
aictx resume --repo . --request "continue current work" --json | python3 -m json.tool
aictx advanced
```

---
priority: important
confidence: high
last_verified: 2026-04-16
tags: aictx, distribution, bootstrap, workspace, install
---

# aictx: distribution and bootstrap

- `aictx install` creates `~/.aictx/` global config and workspace state.
- `aictx init` creates full `.aictx_*` repo-local structure plus starter files.
- Agents should read `.aictx_memory/derived_boot_summary.json` first when present.
- Cross-project operations should use registered workspace roots or repos, never hardcoded host paths.

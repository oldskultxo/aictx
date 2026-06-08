---
title: "AICTX CLI Usage"
description: "Public AICTX commands for setup, agent lifecycle, diagnostics, inspection, and cleanup."
---

# Usage

AICTX is designed for one simple path:

```text
aictx install
aictx init
then let the coding agent work
```

Compatible agents run:

```text
resume -> work -> finalize
```

## Main commands

| Command | Audience | Purpose |
|---|---|---|
| `aictx install` | human/setup | Prepare AICTX runtime/global integration. |
| `aictx init` | human/setup | Initialize one repository and generated agent guidance. |
| `aictx resume --repo . --task "<goal>" --json` | agent | Build the repo-local continuity capsule before work. |
| `aictx finalize --repo . --status success|failure --summary "<summary>" --json` | agent | Persist factual evidence after work. |
| `aictx doctor --repo . --json` | human/CI | Inspect health and recommended repair actions. |
| `aictx view --repo .` | human/agent | Generate local Markdown/Mermaid continuity reports. |
| `aictx clean --repo .` | human | Remove AICTX-managed repo files/blocks. |

## Normal setup

```bash
pip install aictx
aictx install
aictx init
```

For scripts or CI:

```bash
aictx install --yes
aictx init --repo . --yes
```

For first-run details, see [Quickstart](QUICK-START.md) and [Installation](INSTALLATION.md).

## Agent lifecycle

At task startup, agents should pass only the work goal to `--task`:

```bash
aictx resume --repo . --task "fix the parser recovery bug" --json
```

Do not include metrics schemas, benchmark instructions, final-answer format rules, or unrelated prompt wrapper text in `--task`.

After meaningful work:

```bash
aictx finalize --repo . --status success --summary "Fixed parser recovery and ran focused parser tests" --json
```

Use failure status when work did not complete:

```bash
aictx finalize --repo . --status failure --summary "Blocked by failing dependency install; no repo files changed" --json
```

## Inspect and diagnose

```bash
aictx doctor --repo . --json
aictx view --repo .
aictx view --repo . --json
```

`doctor` is read-only. It checks install/init state, runner files, RepoMap status, capture quality, contract compliance health, lifecycle gaps, and stale or obsolete continuity.

`view` writes:

```text
.aictx/reports/continuity-view.md
.aictx/reports/continuity-map.mmd
```

## Advanced supported commands

These commands are supported for inspection, setup variants, and diagnostics. They are not part of the first-run path:

```bash
aictx mcp status --repo .
aictx mcp install --repo .
aictx portability status --repo . --json
aictx portability compact --repo . --apply --json
aictx map status
aictx map refresh
aictx map query "startup banner"
aictx guard ...
aictx steer ...
```

See:

- [MCP](MCP.md)
- [Portability](PORTABILITY.md)
- [RepoMap](REPOMAP.md)
- [Continuity Guard](CONTINUITY_GUARD.md)
- [Steer Guard](STEER_GUARD.md)

## Legacy/internal compatibility

These surfaces are compatibility-only or internal. They are not part of the normal product path and should not be presented as onboarding commands:

- `suggest`, `reuse`, `next`, `reflect`
- task-memory and message-memory commands
- broad `internal ...` commands
- memory-graph and old wrapper scripts
- old report variants not covered by the main `doctor` / `view` flow

They may remain temporarily for compatibility, diagnostics, or migration work, but new users and supported agents should use the main lifecycle commands above.

Do not run exploratory AICTX commands during normal agent startup. Use exactly one continuity query, then finalize at the end.

## Cleanup

Remove repo-local AICTX-managed files and blocks:

```bash
aictx clean --repo .
```

Remove global AICTX-managed setup:

```bash
aictx uninstall
```

For file details, see [What AICTX writes](WHAT-AICTX-WRITES.md).

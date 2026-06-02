---
title: "MCP"
description: "AICTX includes a local Model Context Protocol (MCP) server that exposes repo-local continuity as MCP tools, resources, and prompts."
---

# AICTX MCP

## Model

- Local only: the default transport is `stdio`.
- No cloud service, daemon, account, or API key is required.
- Compatible clients launch the server as a subprocess:

```bash
aictx mcp-server --repo . --profile full
```

The CLI remains the source of truth. MCP tools call the same AICTX runtime functions used by CLI commands.

## Default install/init behavior

`aictx install` prepares AICTX global MCP runtime metadata by default. `aictx init` writes repo-local managed MCP config by default. Sensitive client config is fenced as an AICTX-owned block where the format supports comments:

```toml
# <AICTX:START mcp>
[mcp_servers.aictx]
command = "aictx"
args = ["mcp-server", "--repo", ".", "--profile", "full"]
# <AICTX:END mcp>
```

JSON MCP files cannot carry comment blocks, so AICTX writes explicit `_aictx` / `_aictx_managed` metadata in `.mcp.json` and `.vscode/mcp.json` instead. JSON entries include both `transport: "stdio"` and `type: "stdio"` for client compatibility. In the AICTX source checkout only, the managed entry runs the repo-local module with `PYTHONPATH=src` so MCP attachment uses the current checkout instead of a stale global binary. Use `--no-mcp` to opt out:

```bash
aictx install --no-mcp
aictx init --no-mcp
```

Choose a profile with `--mcp-profile readonly|standard|full`. The default is `full`.

## Profiles

- `readonly`: inspection tools only, such as resume, task context preparation, lifecycle status, next, doctor, Work State read, RepoMap query, portability status, messages status, continuity quality, continuity guard, steer guard, and real usage report.
- `standard`: readonly plus normal lifecycle writes: finalize, Work State start/update/close, and Continuity View generation.
- `full`: standard plus decision, handoff, failure, strategy, RepoMap refresh, portability compact, and messages mode writes.

Full means full AICTX continuity, not full machine control.

## Continuity Quality over MCP

The read-only profile exposes Continuity Quality through:

```text
aictx_continuity_quality
aictx://repo/current/continuity-quality
```

This lets compatible agents inspect whether repo-local continuity is fresh, stale, missing, demoted, obsolete, or unverified before relying on it.

The read-only profile also exposes Continuity Guard through:

```text
aictx_continuity_guard
```

This returns compact `allow`, `caution`, `re_ground`, or `block` guidance before important action boundaries without mutating continuity state or returning the full resume capsule. See [Continuity Guard](CONTINUITY_GUARD.md).

The read-only profile also exposes Steer Guard through:

```text
aictx_steer_guard
```

This classifies user interventions during active agent work and returns compact steering instructions without mutating Work State or contracts. See [Steer Guard](STEER_GUARD.md).

The read-only profile also exposes focused task context preparation through:

```text
aictx_prepare_task_context
```

This tool returns a bounded, non-persistent Task Context Pack for a supplied goal. It is distinct from `aictx_resume`: use `resume` to start lifecycle work; use task context preparation only as an on-demand read-only context compiler that does not write continuity artifacts.

The read-only profile exposes lifecycle diagnostics through:

```text
aictx_lifecycle_status
aictx://repo/current/lifecycle-status
```

Lifecycle status is advisory. It reports incomplete control-loop usage such as resume without finalize, stale active Work State, missing validation evidence, or readonly MCP sessions that never finalized. It does not block users and CLI fallback remains supported.


## Tools, resources, and prompts

Tools cover resume/finalize, Work State, continuity view, decision/handoff/failure memory, RepoMap, portability, messages, and reports. Outputs are JSON-compatible. Write tools include `ok`, `changed`, and `warnings`.

Resources are read-only and use `aictx://repo/current/...` URIs for compact continuity artifacts such as resume capsule, continuity view, work state, failure memory, decisions, handoffs, RepoMap status, and doctor output.

Prompts are short operational prompts for continuing a task, finalizing, debugging failures, reviewing continuity, and preparing releases.

## Security boundaries

The MCP server does not expose arbitrary shell execution, generic file reads/writes, git push/commit, network sync, or cloud sync. Repo paths must resolve to existing directories. Payload sizes are capped, list inputs are bounded, and persisted text is scrubbed for simple secret-like patterns.

## Cleanup

AICTX-managed MCP setup is reversible. Repo-local config is removed by `aictx clean`; AICTX global MCP runtime metadata and comment-delimited `<AICTX>` MCP blocks are removed by `aictx uninstall`. User-authored MCP servers outside AICTX-managed entries are preserved.

## CLI fallback

Generated agent instructions tell compatible agents to prefer AICTX MCP tools when available, call `aictx_resume` before work, call `aictx_finalize` at the end, and fall back to CLI commands when MCP tools are unavailable.

## AICTX 6.11 agent lifecycle enforcement

AICTX 6.11 adds compact runtime metadata to `aictx resume --json`:

- `runner_contract`: AICTX is required, MCP is preferred, CLI fallback is mandatory, and agents should verify `aictx_resume`, `aictx_finalize`, `aictx_continuity_guard`, and `aictx_steer_guard` once per session.
- `guard_triggers`: stable action boundaries for first edit, scope changes, risky commands, user steering, and final answers.
- `execution_contract.validation_policy`: task-type-aware validation expectations so code tasks require focused evidence while documentation and analysis tasks stay advisory.

Routine agent startup can use `aictx resume --repo . --task "<task goal>" --json --brief` for a smaller payload. Standard mode remains the default for compatibility.

Finalize now captures a compact git-state snapshot when Git is available and persists handoffs with `agent_id`, `adapter_id`, `session_id`, and `evidence_quality`.

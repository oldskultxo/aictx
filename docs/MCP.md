# AICTX MCP

AICTX includes a local Model Context Protocol (MCP) server that exposes repo-local continuity as MCP tools, resources, and prompts.

## Model

- Local only: the default transport is `stdio`.
- No cloud service, daemon, account, or API key is required.
- Compatible clients launch the server as a subprocess:

```bash
aictx mcp-server --repo . --profile full
```

The CLI remains the source of truth. MCP tools call the same AICTX runtime functions used by CLI commands.

## Default install/init behavior

`aictx install` prepares AICTX global MCP runtime metadata by default. `aictx init` writes repo-local managed MCP config by default. Use `--no-mcp` to opt out:

```bash
aictx install --no-mcp
aictx init --no-mcp
```

Choose a profile with `--mcp-profile readonly|standard|full`. The default is `full`.

## Profiles

- `readonly`: inspection tools only, such as resume, next, doctor, Work State read, RepoMap query, portability status, messages status, and real usage report.
- `standard`: readonly plus normal lifecycle writes: finalize, Work State start/update/close, and Continuity View generation.
- `full`: standard plus decision, handoff, failure, strategy, RepoMap refresh, portability compact, and messages mode writes.

Full means full AICTX continuity, not full machine control.

## Tools, resources, and prompts

Tools cover resume/finalize, Work State, continuity view, decision/handoff/failure memory, RepoMap, portability, messages, and reports. Outputs are JSON-compatible. Write tools include `ok`, `changed`, and `warnings`.

Resources are read-only and use `aictx://repo/current/...` URIs for compact continuity artifacts such as resume capsule, continuity view, work state, failure memory, decisions, handoffs, RepoMap status, and doctor output.

Prompts are short operational prompts for continuing a task, finalizing, debugging failures, reviewing continuity, and preparing releases.

## Security boundaries

The MCP server does not expose arbitrary shell execution, generic file reads/writes, git push/commit, network sync, or cloud sync. Repo paths must resolve to existing directories. Payload sizes are capped, list inputs are bounded, and persisted text is scrubbed for simple secret-like patterns.

## Cleanup

AICTX-managed MCP setup is reversible. Repo-local config is removed by `aictx clean`; AICTX global MCP runtime metadata is removed by `aictx uninstall`. User-authored MCP servers outside AICTX-managed entries are preserved.

## CLI fallback

Generated agent instructions tell compatible agents to prefer AICTX MCP tools when available, call `aictx_resume` before work, call `aictx_finalize` at the end, and fall back to CLI commands when MCP tools are unavailable.

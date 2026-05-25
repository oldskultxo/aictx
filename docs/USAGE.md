---
title: "AICTX CLI Usage"
description: "Command reference for `aictx` CLI, including setup, resume, finalize, portability, diagnostics, and cleanup workflows."
---

# Usage

This is the command reference.

For normal setup, start with [Installation](INSTALLATION.md). For a fast walkthrough, see [Quickstart](QUICKSTART.md).

---

## Normal use

Normal use is agent-driven:

```bash
pip install aictx
aictx install
aictx init
```

The default interactive setup is compact: `install` asks only about recommended RepoMap/Tree-sitter support, and `init` asks only for repo communication mode. Use `aictx install --manual` or `aictx init --manual` for the full advanced prompt flow.

Then keep using the coding agent.

At normal task startup, supported agents should use one public continuity query:

```bash
aictx resume --repo . --task "<task goal>" --json
```

`--task` is the normal agent startup input. It should contain only the work goal and exclude reporting instructions, metrics schemas, output format rules, benchmark text, logging instructions, and meta-instructions about the final answer. Legacy `--request` startup input has been removed in v6.

`resume` compiles Work State, handoffs, last summary, Strategy Memory, Failure Memory, Decisions, RepoMap, previous contract signals, and an execution contract into one operational capsule. It does not replace prepare/finalize, startup banner rendering, final summary generation, or persistence.

`resume --json` also includes advisory lifecycle status when available. Lifecycle diagnostics can warn about previous sessions that called resume but did not finalize, stale active Work State, missing validation evidence, or MCP resume calls that never closed the loop.

Use `resume` to start lifecycle work. For task-specific read-only context outside the lifecycle startup step, use `prepare`:

```bash
aictx prepare "fix the MCP permissions bug" --repo . --json
```

`prepare` compiles a focused, read-only Task Context Pack for the supplied goal. It uses the same repo-local sources of truth where available, including Work State, handoffs, decisions, failure memory, RepoMap, validation hints, and continuity quality. Unlike `resume`, it does not render startup banner policy, persist a resume contract, write generated trace artifacts, or replace the required `resume -> work -> finalize` lifecycle. If an agent is beginning work, prefer `resume`; if it only needs bounded context, use `prepare`.

In JSON mode, `resume` also includes top-level `loaded_context` metadata. This bounded, additive-only array explains why context was selected, for agent/user inspection and debugging. It can mention active Work State, unresolved carryover, failures, handoffs, decisions, strategies, and RepoMap hints. Items include `role`, `selection_reason`, `confidence`, `staleness`, and `related_paths`. It is not proof of correctness, does not expose hidden reasoning, and does not replace the execution contract.

When RepoMap is enabled and indexed, `resume` can also include `structural_entry_points` and `structural_context`. These are bounded structural hints for where to look first. RepoMap status separates `provider_available`, `index_available`, `query_available`, and `refresh_available`. Execution contracts may include `expected_first_files`, and finalize/contract compliance can record `structural_alignment`. RepoMap remains optional; missing refresh/provider support does not block resume when a queryable index exists.

The normal startup banner source is `resume.startup_banner_text` or `resume.startup_banner_render_payload`. In wrapped execution flows, the source remains `prepare_execution().startup_banner_text`.

The final summary source remains `finalize_execution().agent_summary_text`.

After task work, supported agents should close the lifecycle with the public finalize wrapper:

```bash
aictx finalize --repo . --status success|failure --summary "<what happened>" --json
```

To generate an inspectable local Markdown/Mermaid map of current repo continuity, run:

```bash
aictx view --repo .
```

`aictx view` writes `.aictx/reports/continuity-view.md` and `.aictx/reports/continuity-map.mmd`. It shows active/relevant operational continuity, not just the latest execution. The coding agent may trigger the command, but AICTX generates the Mermaid deterministically from repo-local artifacts. See [Continuity View](CONTINUITY_VIEW.md).

When finalization includes Continuity View links, the agent should append the AICTX final summary with the exact local `continuity-map.mmd` link and exact `mermaid.live view` link returned by AICTX. The agent should not invent, shorten, placeholder, or manually rebuild the Mermaid pako URL.

`aictx finalize` is the normal public CLI surface for finalization. Advanced integrations can still use `aictx internal execution finalize ...` when they already have a prepared execution payload.

For JSON inspection, use a JSON parser:

```bash
aictx resume --repo . --task "continue current work" --json | python3 -m json.tool
```

Do not pipe `--json` into `python3 -`; that asks Python to execute JSON as Python source, where JSON booleans such as `true` are not valid Python names.

---

## Portable continuity for teams

Portable continuity remains opt-in:

```bash
aictx init --repo . --portable-continuity
```

This enables the team-safe portability profile. Git stays the only transport. AICTX exposes append-only/sharded continuity artifacts to Git, keeps conflict-prone latest-run snapshots local-only, and can manage `.gitattributes` merge hints for portable JSONL files.

Portable writes are also secret-safe by default. AICTX redacts detected passwords, tokens, API keys, private keys, credential-bearing URLs, and similar secret-shaped values before persisting the portable subset.

Inspect the active portability policy:

```bash
aictx portability status --repo . --json
```

The status payload can report managed-file drift between `portability.json`, `.gitignore`, and `.gitattributes`.
It can also report portable secret-scan findings without exposing raw secret values.

Compact portable append-only JSONL artifacts after heavy merging:

```bash
aictx portability compact --repo . --apply --json
```

If a portable JSONL file contains invalid rows, compaction reports the blockage and leaves that file unchanged.
If valid rows contain secret-like values, compaction redacts them when it is allowed to rewrite the file.

See [Git-portable continuity](PORTABILITY.md).

---

## Advanced inspection commands

```bash
aictx advanced
aictx resume --repo . --task "continue current work" --json
aictx portability status --repo . --json
aictx portability compact --repo . --apply --json
aictx next
aictx task status --json
aictx map status
aictx doctor --repo . --json
aictx view --repo . --json
aictx report real-usage
```

---

## Public commands

```bash
aictx install
aictx install --manual
aictx init
aictx init --manual
aictx init --portable-continuity
aictx resume --repo . --task "continue current work" --json
aictx finalize --repo . --status success --summary "targeted tests passed" --json
aictx finalize --repo . --status success --summary "targeted tests passed" --include-view --json
aictx view --repo .
aictx view --repo . --mermaid
aictx view --repo . --json
aictx portability status --repo . --json
aictx portability compact --repo . --apply --json
aictx advanced
aictx suggest
aictx reflect
aictx reuse
aictx next
aictx messages status
aictx messages mute
aictx messages unmute
aictx task start "Fix login token refresh"
aictx task status --json
aictx task list --json
aictx task show fix-login-token-refresh --json
aictx task update --json-patch '{"next_action":"run targeted auth tests"}' --json
aictx task update --from-file work-state-patch.json --json
aictx task resume fix-login-token-refresh --json
aictx task close --status resolved --json
aictx map status
aictx map refresh
aictx map query "startup banner"
aictx doctor --repo . --json
aictx view --repo . --json
aictx report real-usage
aictx clean --repo .
aictx uninstall
```

---

## Doctor diagnostics

`aictx doctor` is a read-only support diagnostic. Use `--release-readiness` only for strict aictx release-gate checks.

```bash
aictx doctor --repo . --json
aictx doctor --repo . --release-readiness --json
```

The JSON response has:

```text
status: ok|warning|error
mode: general|release_readiness
checks: [...]
recommended_actions: [...]
```

Default checks include CLI version, repo initialization, runner files, RepoMap provider/index/query/refresh status, capture quality, contract compliance health, lifecycle status, and stale/duplicate memory. `--release-readiness` adds lifecycle smoke compatibility and Makefile/CI compatibility for the aictx release gate.

`doctor` is for humans, support, and CI diagnostics. Normal agents should not call it during startup.

---

## Message controls

AICTX is unmuted by default.

```bash
aictx messages status
aictx messages mute
aictx messages unmute
```

Muted mode suppresses AICTX’s automatic startup banner and execution summary. It does not disable AICTX, memory, telemetry, errors, or explicit command output.

---

## Internal runtime commands

Internal commands are plumbing for integrations:

```bash
aictx internal boot --repo .
aictx internal execution prepare ...
aictx internal execution finalize ...
aictx internal run-execution ...
```

Agents/integrations use these to load and update continuity, including handoffs, decisions, Work State, failure memory, strategy memory, summaries, and contract compliance.

`aictx internal boot --repo .` is a bootstrap/runtime diagnostic payload. It is useful for checking effective preferences, communication policy, runtime state, task/failure/memory graph status, and consistency checks.

The visible startup continuity banner is not the raw boot payload. It is surfaced through prepare/startup continuity as `startup_banner_text`.

The normal agent-facing continuity query is not `internal boot`; it is:

```bash
aictx resume --repo . --task "<task goal>" --json
```

Normal agents should not inspect `.aictx/` or run exploratory AICTX commands at startup. Advanced commands remain available for diagnostics, demos, and explicit user requests.

See [Execution Contracts and Compliance](EXECUTION_CONTRACTS.md) for the contract/compliance flow and [Handoffs and Decisions](HANDOFFS.md) for the continuity artifacts behind startup context.

---

## Strategy Memory commands

```bash
aictx suggest --request "fix startup banner" --json
aictx reuse --request "fix startup banner" --json
```

These commands expose successful historical execution patterns. See [Strategy Memory](STRATEGY_MEMORY.md).

In normal agent startup, Strategy Memory is consumed through `aictx resume`; agents do not need to call `suggest` or `reuse` first.

---

## RepoMap commands

```bash
aictx map status
aictx map refresh
aictx map refresh --full
aictx map query "work state"
aictx map query "work state" --json
```

See [RepoMap](REPOMAP.md).

In normal startup, agents usually do not need to call `map query` directly. `aictx resume` consumes RepoMap as part of the continuity capsule and can render a compact `Structural entry points` section when relevant indexed matches exist.

---

## Contract compliance inspection

Contract compliance is generated by finalize when a compatible resume contract and observable execution signals are available.

Normal agents do not need to run an extra command. To inspect the historical aggregate manually:

```bash
aictx report real-usage
```

Detailed latest rows are stored in:

```text
.aictx/metrics/contract_compliance.jsonl
```

---

## Cleanup

```bash
aictx clean --repo .
aictx uninstall
```

See [Cleanup](CLEANUP.md).

## Using AICTX through MCP

Compatible agents should prefer MCP tools when available: call `aictx_resume` before work, inspect `aictx_lifecycle_status` when warnings are present, and call `aictx_finalize` at the end. If MCP is unavailable, use the equivalent CLI lifecycle: `aictx resume --repo . --task "<task goal>" --json` and `aictx finalize --repo . --status success|failure --summary "<what happened>" --json`.

Public MCP commands:

```bash
aictx mcp status --repo .
aictx mcp status --repo . --json
aictx mcp install --repo .
aictx mcp install --repo . --profile full
aictx mcp install --repo . --dry-run
aictx mcp-server --repo . --profile full
```

## Agent plugins

AICTX ships Claude Code and Codex plugin artifacts. They are MCP-first and CLI-fallback: use `aictx_resume`, `aictx_finalize`, and `aictx_view` when available, otherwise use the AICTX CLI lifecycle. See [Plugins](PLUGINS.md).

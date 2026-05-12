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

Then keep using the coding agent.

At normal task startup, supported agents should use one public continuity query:

```bash
aictx resume --repo . --task "<task goal>" --json
```

`--task` is the normal agent startup input. It should contain only the work goal and exclude reporting instructions, metrics schemas, output format rules, benchmark text, logging instructions, and meta-instructions about the final answer. Legacy `--request` startup input has been removed in v6.

`resume` compiles Work State, handoffs, last summary, Strategy Memory, Failure Memory, Decisions, RepoMap, previous contract signals, and an execution contract into one operational capsule. It does not replace prepare/finalize, startup banner rendering, final summary generation, or persistence.

In JSON mode, `resume` also includes top-level `loaded_context` metadata. This bounded, additive-only array explains why context was selected, for agent/user inspection and debugging. It can mention failures, handoffs, decisions, strategies, and RepoMap hints. It is not proof of correctness, does not expose hidden reasoning, and does not replace the execution contract.

When RepoMap is enabled and indexed, `resume` can also include `structural_entry_points` and `structural_context`. These are bounded structural hints for where to look first. Execution contracts may include `expected_first_files`, and finalize/contract compliance can record `structural_alignment`. RepoMap remains optional; missing or unavailable RepoMap data does not block resume.

The normal startup banner source is `resume.startup_banner_text` or `resume.startup_banner_render_payload`. In wrapped execution flows, the source remains `prepare_execution().startup_banner_text`.

The final summary source remains `finalize_execution().agent_summary_text`.

After task work, supported agents should close the lifecycle with the public finalize wrapper:

```bash
aictx finalize --repo . --status success|failure --summary "<what happened>" --json
```

`aictx finalize` is the normal public CLI surface for finalization. Advanced integrations can still use `aictx internal execution finalize ...` when they already have a prepared execution payload.

For JSON inspection, use a JSON parser:

```bash
aictx resume --repo . --task "continue current work" --json | python3 -m json.tool
```

Do not pipe `--json` into `python3 -`; that asks Python to execute JSON as Python source, where JSON booleans such as `true` are not valid Python names.

---

## Advanced inspection commands

```bash
aictx advanced
aictx resume --repo . --task "continue current work" --json
aictx next
aictx task status --json
aictx map status
aictx report real-usage
```

---

## Public commands

```bash
aictx install
aictx init
aictx resume --repo . --task "continue current work" --json
aictx finalize --repo . --status success --summary "targeted tests passed" --json
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
aictx report real-usage
aictx clean --repo .
aictx uninstall
```

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

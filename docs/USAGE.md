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

---

## Advanced inspection commands

```bash
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
aictx suggest
aictx reflect
aictx reuse
aictx next
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

## Internal runtime commands

Internal commands are plumbing for integrations:

```bash
aictx internal boot --repo .
aictx internal execution prepare ...
aictx internal execution finalize ...
aictx internal run-execution ...
```

Agents/integrations use these to load and update continuity, including handoffs, decisions, Work State, failure memory, strategy memory, and summaries.

`aictx internal boot --repo .` is a bootstrap/runtime diagnostic payload. It is useful for checking effective preferences, communication policy, runtime state, task/failure/memory graph status, and consistency checks.

The visible startup continuity banner is not the raw boot payload. It is surfaced through prepare/startup continuity as `startup_banner_text`.

See [Handoffs and Decisions](HANDOFFS.md) for the continuity artifacts behind startup context.

---

## Strategy Memory commands

```bash
aictx suggest --request "fix startup banner" --json
aictx reuse --request "fix startup banner" --json
```

These commands expose successful historical execution patterns. See [Strategy Memory](STRATEGY_MEMORY.md).

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

---

## Cleanup

```bash
aictx clean --repo .
aictx uninstall
```

See [Cleanup](CLEANUP.md).

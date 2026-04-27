# Cleanup

AICTX provides two cleanup levels:

```bash
aictx clean --repo .
aictx uninstall
```

Cleanup is intentionally conservative, but it can remove local continuity artifacts. Commit or back up anything you want to keep before cleaning.

---

## Clean one repository

```bash
aictx clean --repo .
```

This cleans one repository and unregisters it from AICTX.

It may remove:

```text
.aictx/
.claude/hooks/aictx_session_start.py
.claude/hooks/aictx_user_prompt_submit.py
.claude/hooks/aictx_pre_tool_use.py
.claude/hooks/aictx_refresh_memory_graph.sh
```

It may remove AICTX-managed blocks from:

```text
AGENTS.md
CLAUDE.md
AGENTS.override.md
```

It may update or remove:

```text
.claude/settings.json
.gitignore
```

The cleanup code is designed to remove AICTX-managed content only.

---

## Full uninstall

```bash
aictx uninstall
```

This can:

- clean registered repositories;
- clean workspace references;
- remove AICTX-managed global Codex instruction/config entries;
- remove AICTX global runtime home.

It may touch:

```text
~/.codex/AGENTS.override.md
~/.codex/AICTX_Codex.md
~/.codex/config.toml
```

only for AICTX-managed entries.

---

## What cleanup means for continuity

`aictx clean --repo .` removes `.aictx/`.

That means local continuity artifacts are removed, including Work State, failure memory, strategy memory, metrics, and RepoMap artifacts.

Before cleaning, inspect or commit anything you intend to preserve.

Useful commands:

```bash
git status -- .aictx
aictx task status --json
aictx report real-usage
```

---

## Recommended safe cleanup flow

```bash
git status
aictx task status --json
aictx report real-usage
aictx clean --repo .
```

For full uninstall:

```bash
aictx uninstall
```

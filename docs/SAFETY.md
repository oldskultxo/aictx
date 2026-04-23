# Safety

## Default behavior

- `aictx init` creates or updates repo-local AICTX artifacts.
- Re-running `aictx init` preserves existing logs, feedback, and strategy memory.
- `aictx install` creates AICTX engine home/runtime state only; it does not touch `~/.codex/*` unless explicitly requested.

## Repo-local files AICTX may create or update

- `.ai_context_engine/`
- `AGENTS.md` AICTX-managed block
- `AGENTS.override.md` AICTX-managed block
- `CLAUDE.md` AICTX-managed block
- `.claude/settings.json` AICTX hook entries, merged with existing settings
- `.claude/hooks/aictx_session_start.py`
- `.claude/hooks/aictx_user_prompt_submit.py`
- `.claude/hooks/aictx_pre_tool_use.py`
- `.gitignore` entries for AICTX runtime paths
- `.ai_context_engine/failure_memory/` failure patterns
- `.ai_context_engine/area_memory/` area hints
- `.ai_context_engine/metrics/memory_hygiene.json` non-destructive hygiene report

## Optional global files

Only `aictx install --install-codex-global` may update:

- `~/.codex/AGENTS.override.md`
- `~/.codex/config.toml`

## Managed blocks

Markdown integrations are bounded by:

```md
<!-- AICTX:START -->
...
<!-- AICTX:END -->
```

Cleanup removes only these managed blocks and AICTX-owned hook/config entries. Memory hygiene reports mark duplicate/stale candidates only; they do not delete data.

## What AICTX will not delete during init

- existing `.ai_context_engine/metrics/*.jsonl`
- existing `.ai_context_engine/strategy_memory/*.jsonl`
- unrelated Claude settings or hooks
- unrelated Codex config
- legacy or ad hoc non-AICTX directories

## Cleanup and uninstall

- `aictx clean` removes AICTX-managed content from the current repo only.
- `aictx uninstall` removes AICTX-managed global state and registered repo content.
- Neither command should remove unrelated user files or unmarked config.

# Safety

## Default behavior

- `aictx init` creates or updates repo-local AICTX artifacts.
- Re-running `aictx init` preserves existing logs, feedback, and strategy memory.
- `aictx install` creates AICTX engine home/runtime state only; it does not touch `~/.codex/*` unless explicitly requested.

## Repo-local files AICTX may create or update

- `.aictx/`
- `.aictx/continuity/session.json`
- `.aictx/continuity/handoff.json`
- `.aictx/continuity/decisions.jsonl`
- `.aictx/continuity/semantic_repo.json`
- `.aictx/continuity/dedupe_report.json`
- `.aictx/continuity/staleness.json`
- `.aictx/continuity/continuity_metrics.json`
- `AGENTS.md` AICTX-managed block
- `CLAUDE.md` AICTX-managed block
- `.claude/settings.json` AICTX hook entries, merged with existing settings
- `.claude/hooks/aictx_session_start.py`
- `.claude/hooks/aictx_user_prompt_submit.py`
- `.claude/hooks/aictx_pre_tool_use.py`
- `.gitignore` entries for AICTX runtime paths
- `.aictx/failure_memory/` failure patterns
- `.aictx/area_memory/` area hints
- `.aictx/metrics/memory_hygiene.json` non-destructive hygiene report

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

Cleanup removes only these managed blocks and AICTX-owned hook/config entries. Memory hygiene and staleness reports mark duplicate/stale candidates only; they do not delete history by default.

## What AICTX will not delete during init

- existing `.aictx/metrics/*.jsonl`
- existing `.aictx/strategy_memory/*.jsonl`
- existing `.aictx/continuity/*.json` and `.jsonl` history unless the user explicitly removes AICTX-managed runtime content with cleanup/uninstall
- unrelated Claude settings or hooks
- unrelated Codex config
- legacy or ad hoc non-AICTX directories

## Cleanup and uninstall

- `aictx clean` removes AICTX-managed content from the current repo only.
- `aictx uninstall` removes AICTX-managed global state and registered repo content.
- Neither command should remove unrelated user files or unmarked config.

## Safety posture

- AICTX is a repo-local continuity runtime, not an autonomous repo brain.
- It preserves inspectable artifacts instead of making hidden semantic claims.
- It does not claim guaranteed productivity improvement.
- Correct behavior depends on runner support and agent cooperation with the runtime contract.

# Safety

## Default behavior

- `aictx init` creates or updates repo-local AICTX artifacts
- re-running `aictx init` preserves existing logs, feedback, and strategy memory
- `aictx install` creates AICTX engine home/runtime state only; it does not touch `~/.codex/*` unless explicitly requested

## Repo-local files AICTX may create or update

- `.aictx/`
- `.aictx/continuity/session.json`
- `.aictx/continuity/handoff.json`
- `.aictx/continuity/handoffs.jsonl`
- `.aictx/continuity/decisions.jsonl`
- `.aictx/continuity/semantic_repo.json`
- `.aictx/continuity/dedupe_report.json`
- `.aictx/continuity/staleness.json`
- `.aictx/continuity/continuity_metrics.json`
- `.aictx/continuity/last_execution_summary.md`
- `.aictx/failure_memory/`
- `.aictx/area_memory/`
- `.aictx/metrics/memory_hygiene.json`
- AICTX-managed block inside `AGENTS.md`
- AICTX-managed block inside `CLAUDE.md`
- `.claude/settings.json` merged AICTX hook entries
- `.claude/hooks/aictx_session_start.py`
- `.claude/hooks/aictx_user_prompt_submit.py`
- `.claude/hooks/aictx_pre_tool_use.py`
- `.gitignore` entries for AICTX runtime paths

## Optional global files

Only `aictx install --install-codex-global` may update:

- `~/.codex/AGENTS.override.md`
- `~/.codex/AICTX_Codex.md`
- `~/.codex/config.toml`

## Managed blocks

Markdown integrations are bounded by:

```md
<!-- AICTX:START -->
...
<!-- AICTX:END -->
```

Cleanup removes only managed blocks and AICTX-owned hook/config entries.
Memory hygiene and staleness reports mark candidates only; they do not delete history by default.

## What AICTX will not delete during init

- existing `.aictx/metrics/*.jsonl`
- existing `.aictx/strategy_memory/*.jsonl`
- existing `.aictx/continuity/*.json` and `.jsonl` history unless the user explicitly cleans/uninstalls AICTX content
- unrelated Claude settings or hooks
- unrelated Codex config
- unrelated user files outside AICTX-managed paths/blocks

## Cleanup and uninstall

- `aictx clean --repo <repo>` removes AICTX-managed content from one repository
- `aictx uninstall` removes AICTX-managed global state and registered repo content
- neither command should remove unrelated user files or unmarked config

## Safety posture

- AICTX is a repo-local continuity runtime, not an autonomous repo brain
- it preserves inspectable artifacts instead of hidden semantic claims
- it does not guarantee productivity improvement
- correct behavior still depends on runner support and agent cooperation with the runtime contract

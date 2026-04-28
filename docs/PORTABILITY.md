# Git-portable continuity

AICTX does not sync anything. Git is the transport.

When enabled, AICTX writes a selective `.gitignore` policy that allows committing a safe subset of canonical `.aictx/` artifacts.

## Enable

```bash
aictx init --portable-continuity
```

Interactive setup asks:

```text
Enable AICTX git-portable continuity? [y/N]
```

## Portable artifacts

AICTX can expose this portable subset to Git:

```text
.aictx/tasks/active.json
.aictx/tasks/threads/*.json
.aictx/tasks/threads/*.events.jsonl
.aictx/continuity/portability.json
.aictx/continuity/handoff.json
.aictx/continuity/handoffs.jsonl
.aictx/continuity/decisions.jsonl
.aictx/continuity/semantic_repo.json
.aictx/failure_memory/failure_patterns.jsonl
.aictx/strategy_memory/strategies.jsonl
.aictx/area_memory/areas.json
.aictx/repo_map/config.json
```

## Local-only artifacts

These remain ignored even when portability is enabled:

```text
.aictx/metrics/**
.aictx/continuity/session.json
.aictx/continuity/last_execution_summary.md
.aictx/continuity/continuity_metrics.json
.aictx/continuity/dedupe_report.json
.aictx/continuity/staleness.json
.aictx/repo_map/index.json
.aictx/repo_map/manifest.json
.aictx/repo_map/status.json
```

## Normal flow

Computer A:
- work
- AICTX updates continuity
- git add portable artifacts
- commit/push

Computer B:
- clone/pull
- aictx install
- aictx init
- agent continues with repo-local continuity

## Enabling portability later

You can enable git-portable continuity after a repo was already initialized.

```bash
aictx init --portable-continuity
```

AICTX will:

- preserve existing `.aictx/` artifacts;
- replace the AICTX-managed `.gitignore` block from `local-only` to `portable-continuity`;
- write `.aictx/continuity/portability.json` with `enabled: true`;
- expose only the portable subset to Git.

It will not duplicate, migrate, or reset continuity artifacts.

Existing Work State, handoffs, decisions, failure memory, strategy memory, and RepoMap config stay in their canonical locations.

After enabling portability, inspect what Git can now see:

```bash
git status -- .aictx
```

## Disabling portability later

You can also disable it again:

```bash
aictx init --no-portable-continuity
```

AICTX will:

- preserve existing `.aictx/` artifacts on disk;
- replace the AICTX-managed `.gitignore` block from `portable-continuity` to `local-only`;
- write `.aictx/continuity/portability.json` with `enabled: false`;
- make `.aictx/` ignored again by Git.

This does not delete continuity. It only changes whether the portable subset is visible to Git.

## Safety

Do not commit secrets. Review `.aictx/` changes before committing.

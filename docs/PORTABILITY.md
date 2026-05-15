# Git-portable continuity

AICTX does not sync anything. Git is the transport.

When enabled, AICTX writes a team-safe Git policy that allows committing a safe subset of canonical `.aictx/` artifacts and adds merge hints for append-only JSONL continuity files.

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
.aictx/tasks/threads/*.json
.aictx/tasks/threads/*.events.jsonl
.aictx/continuity/portability.json
.aictx/continuity/handoffs.jsonl
.aictx/continuity/decisions.jsonl
.aictx/continuity/semantic_repo/*.json
.aictx/failure_memory/failure_patterns.jsonl
.aictx/strategy_memory/strategies.jsonl
.aictx/area_memory/areas/*.json
.aictx/repo_map/config.json
```

## Local-only artifacts

These remain ignored even when portability is enabled:

```text
.aictx/metrics/**
.aictx/tasks/active.json
.aictx/continuity/handoff.json
.aictx/continuity/semantic_repo.json
.aictx/area_memory/areas.json
.aictx/continuity/session.json
.aictx/continuity/last_execution_summary.md
.aictx/continuity/continuity_metrics.json
.aictx/continuity/dedupe_report.json
.aictx/continuity/staleness.json
.aictx/continuity/resume_capsule.md
.aictx/continuity/resume_capsule.json
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
- write `.aictx/continuity/portability.json` with `enabled: true`, `policy_version: 2`, `profile: team-safe`, and `merge_policy`;
- write an AICTX-managed `.gitattributes` block for portable JSONL files using Git's `merge=union`;
- expose only the portable subset to Git;
- derive portable history/shards from existing local snapshots when available.

It will not delete or reset continuity artifacts.

Existing Work State, handoffs, decisions, failure memory, strategy memory, and RepoMap config stay in their canonical locations.

After enabling portability, inspect what Git can now see:

```bash
git status -- .aictx
```

Inspect the effective policy:

```bash
aictx portability status --repo . --json
```

Compact portable append-only JSONL after large merges:

```bash
aictx portability compact --repo . --apply --json
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

## Team-safe merge policy

Portable continuity is designed for one engineer or small teams using the same repository.

AICTX keeps generated/latest-run artifacts local-only and exposes durable continuity records. Append-only JSONL artifacts get `.gitattributes` merge hints:

```text
.aictx/tasks/threads/*.events.jsonl merge=union
.aictx/continuity/handoffs.jsonl merge=union
.aictx/continuity/decisions.jsonl merge=union
.aictx/failure_memory/failure_patterns.jsonl merge=union
.aictx/strategy_memory/strategies.jsonl merge=union
```

No external service is required. If a Git client ignores or lacks the merge driver, AICTX still works; the hints only reduce conflicts for independent appends.

Conflict-prone snapshots are local-only in the team-safe profile:

- `.aictx/tasks/active.json` is derived from portable task threads when missing.
- `.aictx/continuity/handoff.json` is derived from `.aictx/continuity/handoffs.jsonl` when missing.
- `.aictx/continuity/semantic_repo.json` is backed by portable subsystem shards under `.aictx/continuity/semantic_repo/*.json`.
- `.aictx/area_memory/areas.json` is backed by portable area shards under `.aictx/area_memory/areas/*.json`.

## Safety

Do not commit secrets. Review `.aictx/` changes before committing.

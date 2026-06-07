---
title: "RepoMap for Coding-Agent Context"
description: "Use AICTX RepoMap to give coding agents lightweight repository structure hints alongside work state and operational memory."
---

# RepoMap

RepoMap is AICTX’s optional structural lookup layer.

It helps answer:

```text
Where should the agent look first?
```

Work State tells the agent what was happening. RepoMap helps locate relevant files and symbols.

---

## What RepoMap does

When enabled, RepoMap can maintain a lightweight structural map of a repository using Tree-sitter support.

It can expose:

- indexed files;
- indexed symbols;
- structural query matches;
- provider availability;
- index availability;
- query availability;
- refresh availability;
- last refresh status.

Commands:

```bash
aictx map status
aictx map refresh
aictx map query "startup banner"
```

---

## RepoMap in resume

When RepoMap is enabled and indexed, `aictx resume` can include structural entry points for the current task:

```bash
aictx resume --repo . --task "improve startup banner handling"
```

Output may include:

```text
Structural entry points:
- src/aictx/middleware/__init__.py
  symbols: prepare_execution
  reasons: repo_map:symbol_match
```

In JSON mode, `resume` exposes the same bounded hints as `structural_entry_points` plus a compact `structural_context` status. Execution contracts can also include `expected_first_files` so finalize/contract compliance can record `structural_alignment`.

RepoMap remains optional. If it is disabled, unavailable, stale, or unindexed, AICTX still loads Work State, Handoffs, Decisions, Failure Memory, internal strategy hints, and the rest of the continuity capsule.

---

## Installation

```bash
pip install "aictx[repomap]"
aictx install
aictx init
```

Interactive `aictx install` recommends RepoMap/Tree-sitter by default. For non-interactive setup, use `aictx install --yes --with-repomap`.

Check status:

```bash
aictx map status --json
```

Status separates provider/refresh capability from index/query capability:

```json
{
  "provider_available": false,
  "index_available": true,
  "query_available": true,
  "refresh_available": false,
  "last_refresh_status": "skipped",
  "files_indexed": 167,
  "symbols_indexed": 1665
}
```

---

## Why it matters

Agents often spend time rediscovering where relevant code lives.

RepoMap gives AICTX a structural source for entry-point hints:

```text
Work State -> continue this task.
Failure Memory -> avoid this known problem.
RepoMap -> start looking here.
```

---

## Runtime artifacts

RepoMap may create:

```text
.aictx/repo_map/config.json
.aictx/repo_map/manifest.json
.aictx/repo_map/index.json
.aictx/repo_map/status.json
```

If Tree-sitter support is unavailable, RepoMap refresh can remain unavailable while the rest of AICTX still works. If a prior index exists, query can still be available even when provider/refresh is not.

---

## Limits

RepoMap:

- is optional;
- depends on Tree-sitter support;
- does not guarantee token savings;
- does not replace Work State or Failure Memory;
- is a structural hint source, not semantic understanding;
- may preserve last-known state when refresh is partial.

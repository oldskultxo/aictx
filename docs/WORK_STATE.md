# Work State

## What it is

Work State is the repo-local artifact for suspended active-task continuity.

It preserves explicit operational state such as:

- goal
- current hypothesis
- active files
- factual verified items
- discarded paths
- next action
- recommended commands
- open risks or uncertainties

AICTX uses it to preserve where active work was mentally left.

## What it is not

Work State is not:

- a planner
- a kanban board
- an issue tracker
- a productivity system
- semantic hidden memory

It is a deterministic, inspectable, repo-local continuity artifact.

## Artifacts

```text
.aictx/tasks/active.json
.aictx/tasks/threads/<task-id>.json
.aictx/tasks/threads/<task-id>.events.jsonl
```

- `active.json` stores the current active task pointer
- `threads/<task-id>.json` stores the normalized current state for that task
- `threads/<task-id>.events.jsonl` stores append-only lifecycle events such as `started`, `updated`, and `closed`

## Public CLI

Examples:

```bash
aictx task start "Fix login token refresh" --repo . --json
aictx task status --repo . --json
aictx task update --repo . --json-patch '{"current_hypothesis":"token not persisted before retry","next_action":"inspect auth interceptor ordering"}' --json
aictx task close --repo . --status resolved --json
```

Supported close statuses:

- `resolved`
- `abandoned`
- `blocked`
- `paused`

`task status --json` returns `{ "active": false }` when no active task exists.

## Runtime integration

`prepare_execution()`:

- loads the active task thread when `.aictx/tasks/active.json` points to a valid task
- exposes compact `active_work_state` in prepared payloads
- makes active Work State visible to startup banner, continuity summary, and `aictx next`

`finalize_execution()`:

- can conservatively update the active task thread from factual execution evidence
- can also accept explicit runtime payloads via `--work-state-json`
- does not invent hypotheses, discarded paths, or product conclusions

## Relationship to other continuity layers

- Work State = current suspended task state
- handoff = latest high-level operational summary
- decisions = explicit architectural/project decisions
- strategy memory = reusable successful procedural patterns
- failure memory = reusable debugging/avoidance context

Priority is intentionally biased toward active Work State when it exists.

## Limits

- only one active task pointer exists per repo at a time
- old task threads remain stored, but AICTX does not turn them into a planner
- automatic finalize updates stay conservative:
  - factual successful commands may become verified entries
  - observed test/build/lint commands may become recommended commands
  - observed files may become active files
- AICTX does not infer hidden intent from sparse evidence

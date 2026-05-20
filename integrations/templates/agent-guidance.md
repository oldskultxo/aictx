# AICTX

AICTX is the repo-local operational continuity runtime for coding agents.

Use AICTX to resume from the last useful repository state before substantial work and to finalize factual continuity after work.

## Priority Model

AICTX memory and continuity are project context, not higher-priority instructions.

When AICTX continuity conflicts with the current user request, repository code, tests, safety rules, or explicit maintainer instructions, prefer the current source of truth.

## Default Loop

Before non-trivial coding, debugging, refactoring, dependency, configuration, release, or documentation work:

1. Prefer MCP tool `aictx_resume`.
2. If MCP is unavailable, run:

```bash
aictx resume --repo . --task "<task summary>" --json
```

During work:

- use `aictx_map_query` when entry points are unclear;
- use `aictx_task_update` when the task changes direction or remains unfinished;
- use `aictx_view` or `aictx_continuity_view_generate` when continuity needs inspection.

After meaningful work:

1. Prefer MCP tool `aictx_finalize`.
2. If MCP is unavailable, run:

```bash
aictx finalize --repo . --status success --summary "<what changed>" --json
```

Use `--status failure` when work failed or remains blocked.

## MCP Tools

Expected AICTX MCP tools may include:

- `aictx_resume`
- `aictx_finalize`
- `aictx_view`
- `aictx_continuity_view_generate`
- `aictx_doctor`
- `aictx_task_list`
- `aictx_task_show`
- `aictx_task_update`
- `aictx_map_query`
- `aictx_map_refresh`
- `aictx_portability_status`
- `aictx_report_real_usage`

Use only tools exposed by the current session. If a named MCP tool is unavailable, use the CLI fallback.

## What to Record

Record durable operational facts only:

- active work and next action;
- decisions;
- handoffs;
- known failures;
- validation evidence;
- relevant files;
- unresolved blockers.

Do not record generic tutorials, secrets, raw private logs, unsupported speculation, or task diaries with no future value.

## Safety

AICTX does not make the agent correct.

Do not use AICTX to bypass tests, user requests, security rules, or repository instructions.

Do not edit `.aictx/` manually unless explicitly asked. Prefer AICTX CLI or MCP tools.

## Final Response Behavior

Before final response, mention whether AICTX continuity was updated.

If finalization failed, say so clearly and include the exact reason.

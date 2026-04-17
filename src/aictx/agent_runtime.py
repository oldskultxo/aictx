from __future__ import annotations

import shutil
from pathlib import Path

from .state import ENGINE_HOME, GLOBAL_METRICS_DIR

AGENTS_START = "<!-- AICTX:START -->"
AGENTS_END = "<!-- AICTX:END -->"
GLOBAL_RUNTIME_PATH = ENGINE_HOME / "agent_runtime.md"
GLOBAL_RUNTIME_MANIFEST_PATH = ENGINE_HOME / "agent_runtime_manifest.json"
LOCAL_RUNTIME_PATH = Path('.ai_context_engine') / 'agent_runtime.md'


def render_agent_runtime(engine_home: Path | None = None) -> str:
    engine_home = engine_home or ENGINE_HOME
    global_metrics_dir = engine_home / ".ai_context_global_metrics"
    return f"""# AI Context Engine agent runtime

Use this runtime guide after repository initialization with `aictx init`.

## Startup / bootstrap
- Read `.ai_context_engine/memory/derived_boot_summary.json` first when present.
- Apply `.ai_context_engine/memory/user_preferences.json` as defaults unless the current prompt overrides them.
- Repo-local preferences may keep communication mode disabled by default; explicit user requests still override.
- `aictx` acts as always-on execution middleware for agent runs in initialized repos: run a base prehook before execution and a base posthook after execution.
- Use the engine as the first low-cost memory layer before deeper repo analysis.
- Do not hand-edit generated `.ai_context_*` artifacts.

## Retrieval order
1. `.ai_context_engine/memory/derived_boot_summary.json`
2. `.ai_context_engine/memory/user_preferences.json`
3. `.ai_context_engine/memory/project_bootstrap.json`
4. smallest relevant note or structured hit
5. code/runtime/tests when memory is missing, stale, or insufficient

## Packet construction
- Use packet-building behavior for non-trivial tasks that need compact context.
- Packet assembly may use retrieval, task memory, failure memory, memory graph, and budget optimization.
- Routing/model suggestion is available when the task complexity needs it.

## Execution middleware
- Enter the engine for every agent execution in initialized repos, even when no skill is active.
- Base prehook: bootstrap + prefs + task classification + minimal retrieval + packet decision.
- Skill-aware enrichment is additive: when explicit skill metadata exists, preserve it and add skill context without changing the always-on entry path.
- Base posthook: telemetry + validated learning write-back + failure/task-memory updates when relevant.
- Heuristic skill detection is low-confidence fallback only; do not treat it as authoritative metadata.
- Repo-local adapter manifests live under `.ai_context_engine/adapters/` and are auto-installed for generic, Codex, and Claude runners.

## Communication mode
- `communication.layer` controls whether the caveman communication layer is active by default: `enabled` or `disabled`.
- `communication.mode` supports `caveman_lite`, `caveman_full`, and `caveman_ultra`.
- Precedence order: explicit current-user instruction > `.ai_context_engine/memory/user_preferences.json` > runtime defaults.
- If `communication.layer=disabled`, use normal style unless the user explicitly asks for caveman mode in the current session.
- Persisted changes to communication mode must come from runtime/preferences updates, not ad-hoc agent assumptions.

## Learning write-back after non-trivial tasks
- Persist validated learnings after non-trivial tasks.
- Prefer updating existing notes/rules over duplicating them.
- Keep generated artifacts derived; write durable knowledge to notes/preferences and regenerate when needed.

## Task memory
- Use task memory to reinforce reusable lessons by task type.
- `unknown` remains the safe fallback bucket.

## Failure memory
- Use failure memory for repeated breakages, regressions, and troubleshooting patterns.
- Reinforce occurrences instead of duplicating failure ids.

## Memory graph
- Use memory graph as a bounded connected-context enrichment layer.
- Graph failure is non-blocking; fallback to normal retrieval layers.

## Knowledge / library / mods
- Activate the knowledge/library workflow only when the user explicitly asks the agent to learn docs, ingest references, or build reusable knowledge.
- When activated, use the library/mods pipeline for local or remote knowledge ingestion and retrieval.

## Savings reports / telemetry / health
- Repo-local sources of truth:
  - `.ai_context_engine/metrics/weekly_summary.json`
  - `CONTEXT_SAVINGS.md` when present
- Global cross-project sources of truth:
  - `{global_metrics_dir / 'projects_index.json'}`
  - `{global_metrics_dir / 'telemetry_sources.json'}`
  - `{global_metrics_dir / 'global_context_savings.json'}`
  - `{global_metrics_dir / 'global_token_savings.json'}`
  - `{global_metrics_dir / 'global_latency_metrics.json'}`
  - `{global_metrics_dir / 'system_health_report.json'}`
- Missing telemetry must be reported as `unknown`, never as zero and never as fabricated estimates.

## Cross-project discovery
- Cross-project discovery must use registered workspace roots or repos.
- Never assume hardcoded host-specific project paths.

## Engine capabilities available after `init`
- boot / bootstrap
- query / retrieval
- packet construction
- route / model suggestion
- migrate / rebuild
- stale detection and compaction analysis
- task memory
- failure memory
- memory graph
- library / mods / retrieval
- global metrics and health
"""


def render_repo_agents_block() -> str:
    return f"""{AGENTS_START}
## AI Context Engine

This repository is initialized for `aictx`.

Agent rules:
- Read `.ai_context_engine/memory/derived_boot_summary.json` first when present.
- Use `aictx` as the first low-cost memory layer before deeper repo analysis.
- Apply `.ai_context_engine/memory/user_preferences.json` as defaults unless the current prompt overrides them.
- Enter the engine middleware for every execution in initialized repos, not only when a skill is active.
- Communication mode may be disabled by repo-local preferences; explicit user requests still override for the current session.
- Persist validated learnings after non-trivial tasks.
- If the user asks the agent to learn docs, reusable knowledge, or external references, activate the knowledge/library workflow.
- If the user asks for savings reports or health, use repo-local `.ai_context_engine/metrics/` and global engine telemetry artifacts as the source of truth.
- Missing telemetry must be reported as `unknown`, never as zero or as an invented estimate.
- Do not hand-edit generated `.ai_context_*` artifacts.

Detailed runtime instructions:
- `.ai_context_engine/agent_runtime.md`
{AGENTS_END}
"""


def render_workspace_agents_block() -> str:
    return f"""{AGENTS_START}
## AI Context Engine Workspace

Workspace rules:
- Repositories initialized with `aictx` may expose `.ai_context_*` artifacts.
- Prefer repo-local bootstrap first, then workspace/global discovery.
- Cross-project reporting must use registered workspace repos or roots, never hardcoded host paths.
- For savings and health, prefer generated telemetry artifacts and report missing data as `unknown`.
{AGENTS_END}
"""


def upsert_marked_block(path: Path, block: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding='utf-8') if path.exists() else ''
    if AGENTS_START in existing and AGENTS_END in existing:
        start = existing.index(AGENTS_START)
        end = existing.index(AGENTS_END) + len(AGENTS_END)
        head = existing[:start].rstrip()
        updated = block.strip() + "\n" if not head else head + "\n\n" + block.strip() + "\n"
        tail = existing[end:].lstrip()
        if tail:
            updated += "\n" + tail
    else:
        updated = existing.rstrip()
        if updated:
            updated += "\n\n"
        updated += block.strip() + "\n"
    path.write_text(updated, encoding='utf-8')


def install_global_agent_runtime(write_json) -> list[Path]:
    ENGINE_HOME.mkdir(parents=True, exist_ok=True)
    GLOBAL_RUNTIME_PATH.write_text(render_agent_runtime(), encoding='utf-8')
    write_json(
        GLOBAL_RUNTIME_MANIFEST_PATH,
        {
            'version': 1,
            'agent_runtime_path': str(GLOBAL_RUNTIME_PATH),
            'global_metrics_dir': str(GLOBAL_METRICS_DIR),
            'managed_agents_markers': [AGENTS_START, AGENTS_END],
            'local_runtime_relative_path': str(LOCAL_RUNTIME_PATH),
        },
    )
    return [GLOBAL_RUNTIME_PATH, GLOBAL_RUNTIME_MANIFEST_PATH]


def copy_local_agent_runtime(repo: Path) -> Path:
    source = GLOBAL_RUNTIME_PATH
    target = repo / LOCAL_RUNTIME_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    return target


def resolve_workspace_root(repo: Path, roots: list[str]) -> Path | None:
    candidates: list[Path] = []
    for root in roots:
        root_path = Path(root).expanduser().resolve()
        try:
            repo.relative_to(root_path)
        except ValueError:
            continue
        candidates.append(root_path)
    if not candidates:
        return None
    return sorted(candidates, key=lambda p: len(p.parts), reverse=True)[0]

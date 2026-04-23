from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from .middleware import finalize_execution, prepare_execution
from .state import ENGINE_HOME

AGENTS_START = "<!-- AICTX:START -->"
AGENTS_END = "<!-- AICTX:END -->"
GLOBAL_RUNTIME_PATH = ENGINE_HOME / "agent_runtime.md"
GLOBAL_RUNTIME_MANIFEST_PATH = ENGINE_HOME / "agent_runtime_manifest.json"
LOCAL_RUNTIME_PATH = Path('.aictx') / 'agent_runtime.md'


def orchestrate_execution_prepare(payload: dict[str, Any]) -> dict[str, Any]:
    return prepare_execution(payload)


def orchestrate_execution_finalize(prepared: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    return finalize_execution(prepared, result)


def render_agent_runtime(engine_home: Path | None = None) -> str:
    engine_home = engine_home or ENGINE_HOME
    return f"""# AI Context Engine agent runtime

Use this runtime guide after repository initialization with `aictx init`.

## Runtime loop
1. Run `prepare_execution` before non-trivial work.
2. Execute the task.
3. Run `finalize_execution` with the real outcome.
4. Append `finalized.agent_summary_text` verbatim to the final user response.
5. If no finalize output exists, say `AICTX summary unavailable`.
6. Reuse previous successful strategies when available.

## Execution middleware
- Enter the runtime for every execution in initialized repos.
- Read `.aictx/metrics/execution_logs.jsonl` for real execution history.
- Read `.aictx/metrics/execution_feedback.jsonl` for real feedback.
- Read `.aictx/strategy_memory/strategies.jsonl` for reusable successful patterns.
- Report missing data as `unknown` instead of inventing values.
- Final responses for non-trivial tasks must include the AICTX summary from finalize.

## aictx usage rules
- Before opening more than 3 files: run `aictx suggest --repo .`
- If you reopen the same file: run `aictx reflect --repo .`
- If the task seems similar to a previous one: run `aictx reuse --repo .`
- If you are unsure about the next step: run `aictx suggest --repo .`

## Communication mode
- `communication.layer` supports `enabled` or `disabled`.
- `communication.mode` supports `caveman_lite`, `caveman_full`, and `caveman_ultra`.
- Explicit current-user instruction overrides persisted defaults.

## Sources of truth
- `.aictx/metrics/execution_logs.jsonl`
- `.aictx/metrics/execution_feedback.jsonl`
- `.aictx/strategy_memory/strategies.jsonl`
"""


def render_repo_agents_block() -> str:
    return f"""{AGENTS_START}
## AI Context Engine

This repository is initialized for `aictx`.

Agent rules:
- Enter the runtime middleware for every execution in initialized repos.
- After finalize, append `agent_summary_text` verbatim to the final user response.
- If no finalize output exists, say `AICTX summary unavailable`.
- Use repo-local execution history and strategy memory before deeper repo analysis.
- Do not hand-edit generated `.aictx_*` artifacts.
- Before opening more than 3 files: run `aictx suggest --repo .`
- If you reopen the same file: run `aictx reflect --repo .`
- If the task seems similar to a previous one: run `aictx reuse --repo .`
- If you are unsure about the next step: run `aictx suggest --repo .`

Detailed runtime instructions:
- `.aictx/agent_runtime.md`
{AGENTS_END}
"""


def render_workspace_agents_block() -> str:
    return f"""{AGENTS_START}
## AI Context Engine Workspace

Workspace rules:
- Repositories initialized with `aictx` may expose `.aictx_*` artifacts.
- Prefer repo-local execution history first.
- Cross-project reporting must use registered workspace repos or roots.
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

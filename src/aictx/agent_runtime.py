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
1. At session start, run exactly one AICTX continuity command: `aictx resume --repo . --request "<current user request>"`.
2. Use the returned continuity capsule as the operational brief.
3. Do not inspect `.aictx/`, do not run exploratory AICTX commands, do not run `aictx internal`, do not run `aictx -h`, and do not run `aictx reuse`, `aictx suggest`, `aictx next`, `aictx task`, `aictx messages`, or `aictx report` during normal task startup.
4. Execute the task.
5. Run `finalize_execution` with the real outcome when using the execution middleware.
6. Append the final AICTX summary to the final user response. When `finalized.agent_summary_policy.render_payload_field` points to `finalized.agent_summary_render_payload`, prefer that structured payload for localization and use `finalized.agent_summary_text` only as the compact fallback source. Localize human-readable prose while preserving exact facts, technical tokens, and the details link/path.
7. If no finalize output exists, say `AICTX summary unavailable`.

## Execution middleware
- Enter the runtime for every execution in initialized repos.
- Use `aictx resume --repo . --request "<current user request>"` for real execution history, feedback, Work State, handoff, RepoMap, failure memory, decision memory, and strategy memory.
- Treat `aictx reuse`, `aictx suggest`, `aictx next`, `aictx task`, `aictx messages`, `aictx report`, and `aictx internal` as advanced/diagnostic/building-block commands, not normal startup commands.
- Report missing data as `unknown` instead of inventing values.
- The startup banner is mandatory on the first execution of each visible session: when `prepared.startup_banner_text` is available, render the startup banner in the current user language. When `prepared.startup_banner_policy.render_payload_field` points to `prepared.startup_banner_render_payload`, prefer that structured payload for localization and use `prepared.startup_banner_text` only as the compact fallback source. You may fully rephrase human-readable prose from structured factual fields while preserving exact facts, file paths, commands, flags, package names, test names, code identifiers, and other technical tokens; do not add, remove, reorder, reinterpret, or invent facts. If first-session text is missing, render `{{agent_label}} · session #{{session_count}} · awake` from prepared identity fields.
- Final responses for non-trivial tasks must include the AICTX summary from finalize; treat `agent_summary_text` as the canonical compact user-facing source.
- For AICTX-originated user-visible texts, prefer `prepared.runtime_text_policy`, `prepared.startup_banner_policy`, and `finalized.agent_summary_policy` when available.
- Localize AICTX-originated user-visible texts to the current user language without hardcoding a fixed language list.
- Do not enrich the final AICTX summary with invented facts; never invent data; prefer structured render payload fields when provided, use compact text fields only as fallback, and preserve file paths, commands, flags, test names, package names, code identifiers, and Markdown details links.

## aictx usage rules
- In the `aictx` source repository, prefer `PYTHONPATH=src .venv/bin/python -m aictx ...` over a globally installed `aictx` binary so the current checkout drives the runtime.
- At normal startup, run only `aictx resume --repo . --request "<current user request>"`.
- Do not inspect `.aictx/` during normal startup; `aictx resume` already compiles the relevant continuity.

## Communication mode
- `communication.layer` supports `enabled` or `disabled`.
- `communication.mode` supports `caveman_lite`, `caveman_full`, and `caveman_ultra`.
- Explicit current-user instruction overrides persisted defaults.

## Sources of truth
- `aictx resume --repo . --request "<current user request>"`
- `.aictx/continuity/resume_capsule.md`
- `.aictx/continuity/resume_capsule.json`
"""


def render_repo_agents_block() -> str:
    return f"""{AGENTS_START}
## AI Context Engine

This repository is initialized for `aictx`.

Agent rules:
- Enter the runtime middleware for every execution in initialized repos.
- At session start, run exactly one AICTX continuity command: `aictx resume --repo . --request "<current user request>"`.
- Use the returned continuity capsule as the operational brief.
- Do not inspect `.aictx/`.
- Do not run exploratory AICTX commands.
- Do not run `aictx internal`, `aictx -h`, `aictx reuse`, `aictx suggest`, `aictx next`, `aictx task`, `aictx messages`, or `aictx report` during normal task startup.
- On the first execution of each visible session, always show the startup banner at the start of the first user-visible response. If `prepare_execution` returns `startup_banner_text`, render the startup banner in the current user language. When `prepared.startup_banner_policy.render_payload_field` points to `prepared.startup_banner_render_payload`, prefer that structured payload for localization and use `prepared.startup_banner_text` only as the compact fallback source. You may fully rephrase human-readable prose from structured factual fields while preserving exact facts, file paths, commands, flags, package names, test names, code identifiers, and other technical tokens; do not add, remove, reorder, reinterpret, or invent facts. If first-session text is missing, render `{{agent_label}} · session #{{session_count}} · awake` from prepared identity fields. Do not render it again after `already_shown` is true.
- After finalize, append the AICTX final summary to the final user response, using `agent_summary_text` as the compact fallback user-facing source. When `agent_summary_policy.render_payload_field` points to `agent_summary_render_payload`, prefer that structured payload for localization while preserving exact facts, technical tokens, and the details link/path.
- If no finalize output exists, say `AICTX summary unavailable`.
- In the `aictx` source repository, prefer `PYTHONPATH=src .venv/bin/python -m aictx ...` over a globally installed `aictx` binary so the current checkout drives the runtime.
- Use the `aictx resume` capsule before deeper repo analysis.
- `.aictx/memory/source/` is editable source knowledge; do not hand-edit generated derived artifacts under `.aictx/boot`, `.aictx/store`, `.aictx/indexes`, `.aictx/metrics`, and similar runtime folders.
- Use `prepared.runtime_text_policy`, `prepared.startup_banner_policy`, and `finalized.agent_summary_policy` when available.
- You may enrich AICTX-originated user-visible texts if helpful, but you must preserve real facts and never invent missing data.
- Advanced/diagnostic/building-block commands remain available for humans and diagnostics, but normal agents should not use them during startup.

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


def write_local_agent_runtime(repo: Path) -> Path:
    target = repo / LOCAL_RUNTIME_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_agent_runtime(), encoding="utf-8")
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

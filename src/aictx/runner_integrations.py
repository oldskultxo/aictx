from __future__ import annotations

import json
import stat
from pathlib import Path

from .agent_runtime import upsert_marked_block

AICTX_START = "<!-- AICTX:START -->"
AICTX_END = "<!-- AICTX:END -->"
CODEX_HOME = Path.home() / ".codex"
CODEX_CONFIG_PATH = CODEX_HOME / "config.toml"


def write_executable(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def render_codex_home_block() -> str:
    return f"""{AICTX_START}
## AICTX Codex integration

When Codex is running inside a repository initialized with `aictx`:
- prefer the repo-local `.ai_context_engine/` runtime before broad repo scanning
- read repo-local `AGENTS.override.md`, `AGENTS.md`, and `.ai_context_engine/agent_runtime.md` when present
- treat `CLAUDE.md` as an additional high-signal project instruction file when available
- for non-trivial tasks, prefer packet/bootstrap guidance derived from `aictx`
- do not hand-edit generated `.ai_context_engine/*` artifacts
- after meaningful code changes, prefer refreshing engine state through `aictx memory-graph --refresh` and `aictx global --refresh`
- if the repository exposes `aictx internal run-execution`, treat it as the preferred middleware entrypoint for wrapped automations
{AICTX_END}
"""


def render_codex_repo_override_block() -> str:
    return f"""{AICTX_START}
## AICTX repo-native Codex instructions

- This repository is initialized with `aictx`; prefer `.ai_context_engine/` as the first memory/runtime layer.
- Read `.ai_context_engine/agent_runtime.md` before deep repo analysis when the task is non-trivial.
- Read `CLAUDE.md` too when it exists; it is part of the repo-level AICTX runtime contract.
- For non-trivial work, prefer packet-oriented context from `aictx packet --task "<task>"`.
- Do not hand-edit generated `.ai_context_engine/*` artifacts.
- Do not recreate parallel memory folders like `.ai_context_memory` or `.ai_context_task_memory`.
- After meaningful writes, prefer `aictx memory-graph --refresh` and `aictx global --refresh`.
- When running wrapped automations, prefer `aictx internal run-execution` as the middleware entrypoint.
- Persist learnings through the engine flow rather than inventing parallel memory files.

## aictx usage rules

- Before opening more than 3 files: run `aictx suggest --repo .`
- If you reopen the same file: run `aictx reflect --repo .`
- If the task seems similar to a previous one: run `aictx reuse --repo .`
- If you are unsure about the next step: run `aictx suggest --repo .`
{AICTX_END}
"""


def render_claude_md_block() -> str:
    return f"""{AICTX_START}
# AICTX Claude integration

This repository is initialized with `aictx`.

- Prefer `.ai_context_engine/` as the first memory/bootstrap layer.
- Use packet-oriented context for non-trivial tasks.
- Claude project hooks may inject bootstrap and packet summaries automatically.
- Pre-tool enforcement may block direct edits to generated runtime artifacts and legacy parallel memory paths.
- Treat `aictx internal run-execution` as the preferred wrapped execution entrypoint when available.

## aictx usage rules

- Before opening more than 3 files: run `aictx suggest --repo .`
- If you reopen the same file: run `aictx reflect --repo .`
- If the task seems similar to a previous one: run `aictx reuse --repo .`
- If you are unsure about the next step: run `aictx suggest --repo .`
{AICTX_END}
"""


def render_claude_settings() -> dict:
    return {
        "hooks": {
            "SessionStart": [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/aictx_session_start.py",
                            "timeout": 20,
                        }
                    ]
                }
            ],
            "UserPromptSubmit": [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/aictx_user_prompt_submit.py",
                            "timeout": 30,
                        }
                    ]
                }
            ],
            "PreToolUse": [
                {
                    "matcher": "Write|Edit|MultiEdit",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/aictx_pre_tool_use.py",
                            "timeout": 20,
                        }
                    ],
                },
                {
                    "matcher": "Bash",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/aictx_pre_tool_use.py",
                            "timeout": 20,
                        }
                    ],
                }
            ],
            "PostToolUse": [
                {
                    "matcher": "Write|Edit|MultiEdit",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/aictx_refresh_memory_graph.sh",
                            "async": True,
                            "timeout": 60,
                        }
                    ],
                }
            ],
        }
    }


def render_session_start_script() -> str:
    return """#!/usr/bin/env python3
import json
import os
import subprocess


def run_json(cmd):
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        return {}
    if proc.returncode != 0:
        return {}
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {}


repo = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
boot = run_json(["aictx", "boot", "--repo", repo])
repo_boot = boot.get("repo_bootstrap", {})
derived = repo_boot.get("derived_boot_summary", {})
project = repo_boot.get("project_bootstrap", {})
memory_graph = boot.get("memory_graph", {})
task_memory = boot.get("task_memory", {})

summary = [
    "AICTX bootstrap loaded automatically for this Claude session.",
    f"Project: {project.get('project') or 'unknown'}",
    f"Bootstrap required: {str(derived.get('bootstrap_required', True)).lower()}",
    f"Task-memory records: {sum((task_memory.get('records_by_task_type') or {}).values()) if isinstance(task_memory.get('records_by_task_type'), dict) else 0}",
    f"Memory-graph nodes: {memory_graph.get('nodes_total', 'unknown')}",
    "Prefer .ai_context_engine/agent_runtime.md and packet-oriented context for non-trivial work.",
]

print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": "\\n".join(summary)
    }
}))
"""


def render_user_prompt_submit_script() -> str:
    return """#!/usr/bin/env python3
import json
import os
import subprocess
import sys


def run_json(cmd):
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        return {}
    if proc.returncode != 0:
        return {}
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {}


payload = json.load(sys.stdin)
prompt = str(payload.get("prompt") or "").strip()
repo = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
if not prompt:
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": "AICTX: empty prompt"}}))
    raise SystemExit(0)

packet = run_json(["aictx", "packet", "--task", prompt])
relevant_memory = packet.get("relevant_memory", [])[:3]
relevant_paths = packet.get("repo_scope", packet.get("relevant_paths", []))[:5]
normalized_paths = []
for path in relevant_paths:
    if isinstance(path, dict):
        value = str(path.get("path") or "").strip()
        if value:
            normalized_paths.append(value)
    elif str(path).strip():
        normalized_paths.append(str(path).strip())
summary = [
    "AICTX packet prepared automatically for this prompt.",
    f"Resolved task type: {packet.get('task_type', 'unknown')}",
    f"Suggested model level: {packet.get('model_suggestion', 'unknown')}",
]
if relevant_memory:
    summary.append("Relevant memory: " + ", ".join(str(item.get("title") or item.get("id") or "") for item in relevant_memory))
if normalized_paths:
    summary.append("Relevant paths: " + ", ".join(normalized_paths))
summary.append("Use .ai_context_engine as first context layer before broad repo scanning.")
summary.append("Before opening more than 3 files or when unsure, run: aictx suggest --repo .")
summary.append("If you reopen the same file, run: aictx reflect --repo .")
summary.append("If the task matches previous work, run: aictx reuse --repo .")

print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "UserPromptSubmit",
        "additionalContext": "\\n".join(summary)
    }
}))
"""


def render_refresh_memory_graph_script() -> str:
    return """#!/bin/sh
set -eu
REPO="${CLAUDE_PROJECT_DIR:-$(pwd)}"
aictx memory-graph --refresh >/dev/null 2>&1 || true
aictx global --refresh >/dev/null 2>&1 || true
exit 0
"""


def render_claude_pre_tool_use_script() -> str:
    return """#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path


GENERATED_PREFIXES = [
    ".ai_context_engine/",
]
LEGACY_MEMORY_DIRS = {
    ".ai_context_memory",
    ".ai_context_cost",
    ".ai_context_task_memory",
    ".ai_context_failure_memory",
    ".ai_context_memory_graph",
    ".ai_context_library",
    ".context_metrics",
}
WRITE_TOOL_NAMES = {"Write", "Edit", "MultiEdit"}


def deny(message: str) -> None:
    sys.stderr.write(message.rstrip() + "\\n")
    raise SystemExit(2)


def normalize_rel(path_str: str, repo_root: Path) -> str:
    raw = Path(path_str)
    if raw.is_absolute():
        try:
            return raw.resolve().relative_to(repo_root.resolve()).as_posix()
        except Exception:
            return raw.as_posix()
    return raw.as_posix().lstrip("./")


def path_is_blocked(rel_path: str) -> bool:
    if any(rel_path == prefix.rstrip("/") or rel_path.startswith(prefix) for prefix in GENERATED_PREFIXES):
        return True
    first = rel_path.split("/", 1)[0]
    return first in LEGACY_MEMORY_DIRS


payload = json.load(sys.stdin)
repo_root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()).resolve()
tool_name = str(payload.get("tool_name") or "")
tool_input = payload.get("tool_input", {}) if isinstance(payload.get("tool_input"), dict) else {}

if tool_name in WRITE_TOOL_NAMES:
    file_path = str(tool_input.get("file_path") or "")
    rel_path = normalize_rel(file_path, repo_root)
    if path_is_blocked(rel_path):
        deny(
            "AICTX policy: generated runtime artifacts and legacy parallel memory directories must not be edited directly. "
            "Update durable notes/rules instead and let aictx regenerate derived state."
        )

if tool_name == "Bash":
    command = str(tool_input.get("command") or "")
    lowered = command.lower()
    risky_tokens = ["rm ", "mv ", "cp ", "sed ", "perl ", "python ", "python3 ", "cat >", "> ", ">> ", "tee "]
    mentions_generated = ".ai_context_engine/" in command or any(name in command for name in LEGACY_MEMORY_DIRS)
    if mentions_generated and any(token in lowered for token in risky_tokens):
        deny(
            "AICTX policy: do not mutate generated runtime artifacts or legacy memory folders from Bash. "
            "Use aictx-owned flows and refresh commands instead."
        )

raise SystemExit(0)
"""


def ensure_codex_config_hardening() -> list[Path]:
    CODEX_HOME.mkdir(parents=True, exist_ok=True)
    if CODEX_CONFIG_PATH.exists():
        existing = CODEX_CONFIG_PATH.read_text(encoding="utf-8")
    else:
        existing = ""
    managed_comment = "# AICTX managed fallback docs for stronger repo instruction loading"
    desired = 'project_doc_fallback_filenames = ["CLAUDE.md"]'
    if "project_doc_fallback_filenames" in existing:
        return [CODEX_CONFIG_PATH]
    updated = existing.rstrip()
    if updated:
        updated += "\n\n"
    updated += managed_comment + "\n" + desired + "\n"
    CODEX_CONFIG_PATH.write_text(updated, encoding="utf-8")
    return [CODEX_CONFIG_PATH]


def install_codex_native_integration() -> list[Path]:
    path = CODEX_HOME / "AGENTS.override.md"
    upsert_marked_block(path, render_codex_home_block())
    created = [path]
    created.extend(ensure_codex_config_hardening())
    return created


def install_repo_runner_integrations(repo: Path) -> list[Path]:
    created: list[Path] = []

    codex_override = repo / "AGENTS.override.md"
    upsert_marked_block(codex_override, render_codex_repo_override_block())
    created.append(codex_override)

    claude_md = repo / "CLAUDE.md"
    upsert_marked_block(claude_md, render_claude_md_block())
    created.append(claude_md)

    claude_settings = repo / ".claude" / "settings.json"
    claude_settings.parent.mkdir(parents=True, exist_ok=True)
    claude_settings.write_text(json.dumps(render_claude_settings(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    created.append(claude_settings)

    session_start = repo / ".claude" / "hooks" / "aictx_session_start.py"
    write_executable(session_start, render_session_start_script())
    created.append(session_start)

    user_prompt = repo / ".claude" / "hooks" / "aictx_user_prompt_submit.py"
    write_executable(user_prompt, render_user_prompt_submit_script())
    created.append(user_prompt)

    pre_tool = repo / ".claude" / "hooks" / "aictx_pre_tool_use.py"
    write_executable(pre_tool, render_claude_pre_tool_use_script())
    created.append(pre_tool)

    refresh_graph = repo / ".claude" / "hooks" / "aictx_refresh_memory_graph.sh"
    write_executable(refresh_graph, render_refresh_memory_graph_script())
    created.append(refresh_graph)

    return created

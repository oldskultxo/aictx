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
- prefer repo-local execution history and strategy memory before broad repo scanning
- read repo-local `AGENTS.override.md`, `AGENTS.md`, and `.ai_context_engine/agent_runtime.md` when present
- treat `CLAUDE.md` as an additional high-signal project instruction file when available
- do not hand-edit generated `.ai_context_engine/*` artifacts
- if the repository exposes `aictx internal run-execution`, treat it as the preferred middleware entrypoint for wrapped automations
{AICTX_END}
"""


def render_codex_repo_override_block() -> str:
    return f"""{AICTX_START}
## AICTX repo-native Codex instructions

- This repository is initialized with `aictx`; prefer `.ai_context_engine/` as the first runtime layer.
- Read `.ai_context_engine/agent_runtime.md` before deep repo analysis when the task is non-trivial.
- Read `CLAUDE.md` too when it exists; it is part of the repo-level AICTX runtime contract.
- Use `.ai_context_engine/metrics/` and `.ai_context_engine/strategy_memory/` as the source of truth.
- Do not hand-edit generated `.ai_context_engine/*` artifacts.
- Do not recreate parallel memory folders.
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

- Use repo-local execution history and strategy memory for non-trivial tasks.
- Claude project hooks may inject runtime guidance automatically.
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
            "SessionStart": [{"hooks": [{"type": "command", "command": '"$CLAUDE_PROJECT_DIR"/.claude/hooks/aictx_session_start.py', "timeout": 20}]}],
            "UserPromptSubmit": [{"hooks": [{"type": "command", "command": '"$CLAUDE_PROJECT_DIR"/.claude/hooks/aictx_user_prompt_submit.py', "timeout": 30}]}],
            "PreToolUse": [
                {"matcher": "Write|Edit|MultiEdit", "hooks": [{"type": "command", "command": '"$CLAUDE_PROJECT_DIR"/.claude/hooks/aictx_pre_tool_use.py', "timeout": 20}]},
                {"matcher": "Bash", "hooks": [{"type": "command", "command": '"$CLAUDE_PROJECT_DIR"/.claude/hooks/aictx_pre_tool_use.py', "timeout": 20}]},
            ],
        }
    }


def render_session_start_script() -> str:
    return """#!/usr/bin/env python3
import json

summary = [
    "AICTX runtime loaded for this Claude session.",
    "Prefer .ai_context_engine/metrics/execution_logs.jsonl as real execution history.",
    "Prefer .ai_context_engine/strategy_memory/strategies.jsonl for reusable patterns.",
    "Use aictx suggest/reuse/reflect when needed.",
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

suggest = run_json(["aictx", "suggest", "--repo", repo])
reuse = run_json(["aictx", "reuse", "--repo", repo])
summary = [
    "AICTX runtime guidance loaded for this prompt.",
    "Use execution history and strategy memory before broad repo scanning.",
]
entry_points = suggest.get("suggested_entry_points", []) if isinstance(suggest, dict) else []
if entry_points:
    summary.append("Suggested entry points: " + ", ".join(str(item) for item in entry_points))
files_used = reuse.get("files_used", []) if isinstance(reuse, dict) else []
if files_used:
    summary.append("Reusable files: " + ", ".join(str(item) for item in files_used[:5]))
summary.append("Before opening more than 3 files or when unsure, run: aictx suggest --repo .")
summary.append("If you reopen the same file several times, run: aictx reflect --repo .")
summary.append("If the task matches previous work, run: aictx reuse --repo .")

print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "UserPromptSubmit",
        "additionalContext": "\\n".join(summary)
    }
}))
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
            "Use aictx-owned flows instead."
        )

raise SystemExit(0)
"""


def ensure_codex_config_hardening() -> list[Path]:
    CODEX_HOME.mkdir(parents=True, exist_ok=True)
    existing = CODEX_CONFIG_PATH.read_text(encoding="utf-8") if CODEX_CONFIG_PATH.exists() else ""
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

    return created

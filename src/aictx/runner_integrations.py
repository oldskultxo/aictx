from __future__ import annotations

import json
import stat
from pathlib import Path
from typing import Any

from .agent_runtime import upsert_marked_block
from .generated_paths import GENERATED_RUNTIME_DIRS
from .integrations.mcp_config import DEFAULT_MCP_PROFILE, mcp_server_command

AICTX_START = "<!-- AICTX:START -->"
AICTX_END = "<!-- AICTX:END -->"
AICTX_CONFIG_START = "# <AICTX:START mcp>"
AICTX_CONFIG_END = "# <AICTX:END mcp>"
CODEX_HOME = Path.home() / ".codex"
CODEX_CONFIG_PATH = CODEX_HOME / "config.toml"
CLAUDE_GITIGNORE_COMMENT = "# AICTX managed Claude repo integration"
CLAUDE_DIR_GITIGNORE_LINE = ".claude/"
CLAUDE_MD_GITIGNORE_LINE = "CLAUDE.md"
COPILOT_INSTRUCTIONS_PATH = Path(".github") / "copilot-instructions.md"
COPILOT_PATH_INSTRUCTIONS_PATH = Path(".github") / "instructions" / "aictx.instructions.md"
COPILOT_RESUME_PROMPT_PATH = Path(".github") / "prompts" / "aictx-resume.prompt.md"
COPILOT_FINALIZE_PROMPT_PATH = Path(".github") / "prompts" / "aictx-finalize.prompt.md"


def render_mcp_first_startup_rule() -> str:
    return (
        "MCP-first startup: if AICTX MCP tools are already visible, use those tools for resume/finalize. "
        "If they are not visible but `.mcp.json` or `.vscode/mcp.json` exists, first use the runner tool-discovery mechanism when available (for example search for `aictx resume finalize lifecycle`) so lazy-loaded MCP namespaces can attach, then have the runner attach/start the configured stdio MCP server before the first AICTX command of each new session. "
        "If MCP tools still are not attached after discovery/attachment, state that MCP config exists but tools are unavailable in this runner and use the CLI fallback."
    )


def render_codex_mcp_config_block(profile: str = DEFAULT_MCP_PROFILE) -> str:
    command = mcp_server_command(profile) + ["--agent-id", "codex", "--adapter-id", "codex"]
    args = ", ".join(json.dumps(arg) for arg in command[1:])
    return "\n".join(
        [
            AICTX_CONFIG_START,
            "# AICTX managed MCP server for repo-local continuity; safe to remove as one block.",
            "[mcp_servers.aictx]",
            f"command = {json.dumps(command[0])}",
            f"args = [{args}]",
            AICTX_CONFIG_END,
        ]
    )


def write_executable(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def codex_instructions_path() -> Path:
    return CODEX_HOME / "AICTX_Codex.md"


def render_aictx_lifecycle_rules(*, agent_id: str, adapter_id: str, include_source_repo_hint: bool = True) -> str:
    rules = [
        "- Prefer AICTX MCP tools when available; fall back to AICTX CLI commands otherwise.",
        f"- {render_mcp_first_startup_rule()}",
        "- The lifecycle remains `resume -> work -> finalize -> final AICTX summary/persistence`.",
        f'- At session start, run exactly one AICTX continuity command: `aictx resume --repo . --task "<task goal>" --agent-id {agent_id} --adapter-id {adapter_id} --json`.',
        "- Use the returned resume capsule as the operational brief before broad repo scanning.",
        f'- After work, run exactly one AICTX finalization command: `aictx finalize --repo . --status success|failure --summary "<what happened>" --agent-id {agent_id} --adapter-id {adapter_id} --json`.',
        "- Do not inspect `.aictx/` during normal startup.",
        "- Do not run exploratory AICTX commands during normal startup.",
        "- If `startup_banner_policy.show_in_first_user_visible_response` is true, render the selected startup banner at the start of the first substantive user-visible response.",
        "- Prefer `startup_banner_render_payload` when present; use `startup_banner_text` as fallback.",
        "- After finalize, append the AICTX final summary using `agent_summary_render_payload` when present; use `agent_summary_text` as fallback.",
    ]
    if include_source_repo_hint:
        rules.append("- In the `aictx` source repository, prefer `PYTHONPATH=src .venv/bin/python -m aictx ...` over a global `aictx` binary.")
    return "\n".join(rules)


def render_codex_home_block() -> str:
    return f"""{AICTX_START}
## AICTX Codex integration

When Codex is running inside a repository initialized with `aictx`:
- Prefer AICTX MCP tools when available; fall back to AICTX CLI commands otherwise.
- {render_mcp_first_startup_rule()}
- the lifecycle remains `prepare/startup context → resume capsule → work → finalize → final AICTX summary/persistence`
- at session start, run exactly one AICTX continuity command: `aictx resume --repo . --task "<task goal>" --json`
- use the returned continuity capsule as the operational brief before broad repo scanning
- Render exactly one startup banner source: normal agent startup uses `resume.startup_banner_text` or `resume.startup_banner_render_payload`; wrapped execution uses `prepare_execution().startup_banner_text` or `prepare_execution().startup_banner_render_payload`. Do not render both
- `resume` is the canonical agent-facing continuity query; it does not replace `prepare_execution`, `finalize_execution`, the startup banner, the final AICTX summary, or persistence
- do not inspect `.aictx/` during normal startup
- treat `CLAUDE.md` as an additional high-signal project instruction file when available
- `.aictx/memory/source/` is editable source knowledge; avoid hand-editing generated `.aictx/boot`, `.aictx/store`, `.aictx/indexes`, `.aictx/metrics`, and similar derived artifacts
- do not run `aictx internal`, `aictx -h`, `aictx reuse`, `aictx suggest`, `aictx next`, `aictx task`, `aictx messages`, `aictx reflect`, or `aictx report` during normal task startup unless the user asks for AICTX diagnostics, the task is about AICTX itself, resume is missing/corrupt/contradictory, or finalization/update lifecycle requires it
- on the first execution of each visible session, always show the startup banner at the start of the first substantive user-visible response; do not consume it with a transient progress/status message that will be omitted from the final task response; render the selected resume/prepare startup banner in the current user language. When the selected startup banner policy points to a structured render payload, prefer that structured payload for localization and use compact text only as the fallback source. You may fully rephrase human-readable prose from structured factual fields while preserving exact facts, file paths, commands, flags, package names, test names, code identifiers, and other technical tokens; do not add, remove, reorder, reinterpret, or invent facts. If first-session text is missing, render `{{agent_label}} · session #{{session_count}} · awake` from selected identity fields; do not render it again after `already_shown` is true
- in the `aictx` source repository, prefer `PYTHONPATH=src .venv/bin/python -m aictx ...` over a globally installed `aictx` binary so the current checkout drives the runtime
- final responses for non-trivial tasks must include the AICTX final summary from finalize, using `agent_summary_text` as the compact fallback user-facing source. When `finalized.agent_summary_policy.render_payload_field` points to `finalized.agent_summary_render_payload`, prefer that structured payload for localization while preserving exact facts, technical tokens, and the details/continuity link targets; render every provided summary section, including `details`, `continuity_view_file`, and `continuity_view_online`; do not replace Mermaid URLs with placeholders and do not manually reconstruct or retype pako URLs; if unavailable, say `AICTX summary unavailable`
{AICTX_END}
"""


def render_codex_global_instructions() -> str:
    return f"""# AICTX Codex global developer instructions

Use AICTX in every Codex session for repositories initialized with `aictx`.

Required behavior:
- Prefer AICTX MCP tools when available; fall back to AICTX CLI commands otherwise.
- {render_mcp_first_startup_rule()}
- Do not decide whether AICTX applies. If the repository contains `.aictx/`, use it.
- The lifecycle remains `prepare/startup context → resume capsule → work → finalize → final AICTX summary/persistence`.
- At session start, run exactly one AICTX continuity command: `aictx resume --repo . --task "<task goal>" --json`.
- Use the returned continuity capsule as the operational brief.
- Render exactly one startup banner source: normal agent startup uses `resume.startup_banner_text` or `resume.startup_banner_render_payload`; wrapped execution uses `prepare_execution().startup_banner_text` or `prepare_execution().startup_banner_render_payload`. Do not render both.
- `resume` is the canonical agent-facing continuity query; it does not replace `prepare_execution`, `finalize_execution`, the startup banner, the final AICTX summary, or persistence.
- Do not inspect `.aictx/` during normal startup.
- Do not run exploratory AICTX commands.
- Do not run `aictx internal`, `aictx -h`, `aictx reuse`, `aictx suggest`, `aictx next`, `aictx task`, `aictx messages`, `aictx reflect`, or `aictx report` during normal task startup unless the user asks for AICTX diagnostics, the task is about AICTX itself, resume is missing/corrupt/contradictory, or finalization/update lifecycle requires it.
- Read `CLAUDE.md` too when it exists.
- On the first execution of each visible session, always place the startup banner at the start of the first substantive user-visible response; do not consume it with a transient progress/status message that will be omitted from the final task response. Render the selected resume/prepare startup banner in the current user language. When the selected startup banner policy points to a structured render payload, prefer that structured payload for localization and use compact text only as the fallback source. You may fully rephrase human-readable prose from structured factual fields while preserving exact facts, file paths, commands, flags, package names, test names, code identifiers, and other technical tokens; do not add, remove, reorder, reinterpret, or invent facts. If first-session text is missing, render `{{agent_label}} · session #{{session_count}} · awake` from selected identity fields. Do not render it again after `already_shown` is true.
- Final responses for non-trivial tasks must append the AICTX final summary after finalize, using `agent_summary_text` as the compact fallback user-facing source. When `finalized.agent_summary_policy.render_payload_field` points to `finalized.agent_summary_render_payload`, prefer that structured payload for localization while preserving exact facts, technical tokens, and the details/continuity link targets. Render every provided summary section, including `details`, `continuity_view_file`, and `continuity_view_online`; do not replace Mermaid URLs with placeholders and do not manually reconstruct or retype pako URLs.
- If finalize output is unavailable, say exactly `AICTX summary unavailable`.
- In the `aictx` source repository, prefer `PYTHONPATH=src .venv/bin/python -m aictx ...` over a globally installed `aictx` binary so the current checkout drives the runtime.
"""


def render_claude_md_block() -> str:
    return f"""{AICTX_START}
# AICTX Claude integration

This repository is initialized with `aictx`.

- Prefer AICTX MCP tools when available; fall back to AICTX CLI commands otherwise.
- {render_mcp_first_startup_rule()}
- The lifecycle remains `prepare/startup context → resume capsule → work → finalize → final AICTX summary/persistence`.
- At session start, run exactly one AICTX continuity command: `aictx resume --repo . --task "<task goal>" --json`.
- Use the returned continuity capsule as the operational brief.
- Render exactly one startup banner source: normal agent startup uses `resume.startup_banner_text` or `resume.startup_banner_render_payload`; wrapped execution uses `prepare_execution().startup_banner_text` or `prepare_execution().startup_banner_render_payload`. Do not render both.
- `resume` is the canonical agent-facing continuity query; it does not replace `prepare_execution`, `finalize_execution`, the startup banner, the final AICTX summary, or persistence.
- Do not inspect `.aictx/` during normal startup.
- Claude project hooks may inject runtime guidance automatically.
- Pre-tool enforcement may block direct edits to generated runtime artifacts.
- Do not run `aictx internal`, `aictx -h`, `aictx reuse`, `aictx suggest`, `aictx next`, `aictx task`, `aictx messages`, `aictx reflect`, or `aictx report` during normal task startup unless the user asks for AICTX diagnostics, the task is about AICTX itself, resume is missing/corrupt/contradictory, or finalization/update lifecycle requires it.
- On the first execution of each visible session, always show the startup banner at the start of the first substantive user-visible response; do not consume it with a transient progress/status message that will be omitted from the final task response. Render the selected resume/prepare startup banner in the current user language. When the selected startup banner policy points to a structured render payload, prefer that structured payload for localization and use compact text only as the fallback source. You may fully rephrase human-readable prose from structured factual fields while preserving exact facts, file paths, commands, flags, package names, test names, code identifiers, and other technical tokens; do not add, remove, reorder, reinterpret, or invent facts. If first-session text is missing, render `{{agent_label}} · session #{{session_count}} · awake` from selected identity fields. Do not render it again after `already_shown` is true.
- After finalize, append the AICTX final summary to the final user response, using `agent_summary_text` as the compact fallback user-facing source. When `finalized.agent_summary_policy.render_payload_field` points to `finalized.agent_summary_render_payload`, prefer that structured payload for localization while preserving exact facts, technical tokens, and the details/continuity link targets. Render every provided summary section, including `details`, `continuity_view_file`, and `continuity_view_online`; do not replace Mermaid URLs with placeholders and do not manually reconstruct or retype pako URLs.
- If no finalize output exists, say `AICTX summary unavailable`.
- In the `aictx` source repository, prefer `PYTHONPATH=src .venv/bin/python -m aictx ...` over a globally installed `aictx` binary so the current checkout drives the runtime.

## aictx usage rules

- At normal startup, run only `aictx resume --repo . --task "<task goal>" --json`
- Render exactly one startup banner source. Normal agent startup uses `resume.startup_banner_text` or `resume.startup_banner_render_payload`. Wrapped execution uses `prepare_execution().startup_banner_text` or `prepare_execution().startup_banner_render_payload`. Do not render both.
- Treat `aictx reflect` and other AICTX commands as advanced diagnostics, not normal startup commands.
{AICTX_END}
"""


def render_copilot_instructions_block() -> str:
    return f"""{AICTX_START}
# AICTX GitHub Copilot integration

These are repository custom instructions for GitHub Copilot. AICTX cannot force Copilot to run commands, but Copilot should follow this lifecycle whenever command execution is available.

Critical lifecycle:
- Prefer AICTX MCP tools when available; fall back to AICTX CLI commands otherwise.
- {render_mcp_first_startup_rule()}
- For non-trivial repository tasks, first run exactly once: `aictx resume --repo . --task "<task goal>" --agent-id copilot --adapter-id copilot-vscode --json`.
- Use the returned resume capsule as the operational brief before broad repo scanning.
- Before the final response, run exactly once: `aictx finalize --repo . --status success|failure --summary "<what happened>" --agent-id copilot --adapter-id copilot-vscode --json`.
- Append the AICTX final summary from finalize when available. Render every provided summary section, including `details`, `continuity_view_file`, and `continuity_view_online`; preserve Continuity View file links and Mermaid online view links; do not replace URLs with placeholders and do not manually reconstruct or retype pako URLs. If command execution is unavailable, say that the AICTX lifecycle could not be executed.
- Do not inspect `.aictx/` directly during normal startup; use `aictx resume`.
- Do not run exploratory AICTX commands during normal startup.
- In the `aictx` source repository, prefer `PYTHONPATH=src .venv/bin/python -m aictx ...` over a global `aictx` binary.

Verification tip: in Copilot Chat, expand response References and confirm `.github/copilot-instructions.md` is listed.
{AICTX_END}
"""


def render_copilot_path_instructions_file() -> str:
    return f"""---
applyTo: "**/*"
---

{AICTX_START}
# AICTX Copilot path-specific lifecycle

Apply these instructions to repository work. Prefer AICTX MCP tools when available; fall back to AICTX CLI commands otherwise. They intentionally duplicate the minimal AICTX lifecycle because Copilot support varies by surface.

- {render_mcp_first_startup_rule()}
- Start non-trivial repository tasks with: `aictx resume --repo . --task "<task goal>" --agent-id copilot --adapter-id copilot-vscode --json`.
- Use the resume capsule before broad repo scanning.
- Finalize non-trivial repository tasks with: `aictx finalize --repo . --status success|failure --summary "<what happened>" --agent-id copilot --adapter-id copilot-vscode --json`.
- Append the AICTX final summary from finalize when available. Render every provided summary section, including `details`, `continuity_view_file`, and `continuity_view_online`; preserve Continuity View file links and Mermaid online view links; do not replace URLs with placeholders and do not manually reconstruct or retype pako URLs.
- If command execution is unavailable, state that the AICTX lifecycle could not be executed.
- Do not inspect `.aictx/` directly during normal startup.
{AICTX_END}
"""


def render_copilot_resume_prompt() -> str:
    return f"""{AICTX_START}
# AICTX resume prompt

Use this prompt when starting a non-trivial GitHub Copilot repository task.

1. Extract the task goal from the user request.
2. If AICTX MCP tools are already visible, use the MCP resume tool. If they are not visible but `.mcp.json` or `.vscode/mcp.json` exists, have the runner attach/start the configured stdio MCP server before falling back.
3. If MCP tools are unavailable, run:

```bash
aictx resume --repo . --task "<task goal>" --agent-id copilot --adapter-id copilot-vscode --json
```

4. Use the returned capsule as the operational brief before broad repo scanning.
5. Do not inspect `.aictx/` directly during normal startup.
{AICTX_END}
"""


def render_copilot_finalize_prompt() -> str:
    return f"""{AICTX_START}
# AICTX finalize prompt

Use this prompt before the final response for a non-trivial GitHub Copilot repository task.

1. Summarize what happened factually.
2. Prefer the AICTX MCP finalize tool if it is attached.
3. If MCP tools are unavailable, run:

```bash
aictx finalize --repo . --status success|failure --summary "<what happened>" --agent-id copilot --adapter-id copilot-vscode --json
```

4. Append the AICTX final summary when available. Render every provided summary section, including `details`, `continuity_view_file`, and `continuity_view_online`; preserve Continuity View file links and Mermaid online view links; do not replace URLs with placeholders and do not manually reconstruct or retype pako URLs.
5. If finalize cannot run, say that the AICTX lifecycle could not be completed.
{AICTX_END}
"""


def upsert_copilot_path_instructions(path: Path) -> None:
    preamble = '---\napplyTo: "**/*"\n---\n\n'
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if not existing.startswith("---\n") or "applyTo:" not in existing.split("---", 2)[1]:
            path.write_text(preamble + existing.lstrip(), encoding="utf-8")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(preamble, encoding="utf-8")
    block = render_copilot_path_instructions_file().split("---\n", 2)[2].lstrip()
    upsert_marked_block(path, block)


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


def _json_key(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def merge_claude_settings(existing: dict[str, Any], desired: dict[str, Any] | None = None) -> dict[str, Any]:
    merged: dict[str, Any] = dict(existing) if isinstance(existing, dict) else {}
    desired_payload = desired or render_claude_settings()
    existing_hooks = merged.get("hooks")
    if not isinstance(existing_hooks, dict):
        existing_hooks = {}
    merged_hooks: dict[str, Any] = dict(existing_hooks)
    desired_hooks = desired_payload.get("hooks", {}) if isinstance(desired_payload, dict) else {}
    for event_name, desired_entries in desired_hooks.items():
        if not isinstance(desired_entries, list):
            continue
        current_entries = merged_hooks.get(event_name)
        if not isinstance(current_entries, list):
            current_entries = []
        updated_entries = list(current_entries)
        seen = {_json_key(entry) for entry in updated_entries}
        for entry in desired_entries:
            key = _json_key(entry)
            if key not in seen:
                updated_entries.append(entry)
                seen.add(key)
        merged_hooks[event_name] = updated_entries
    merged["hooks"] = merged_hooks
    return merged


def write_merged_claude_settings(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing: dict[str, Any] = {}
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                existing = payload
        except json.JSONDecodeError:
            existing = {}
    path.write_text(json.dumps(merge_claude_settings(existing), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def ensure_gitignore_claude_if_created(
    repo: Path,
    *,
    claude_dir_preexisted: bool,
    claude_md_preexisted: bool,
) -> Path | None:
    gitignore_path = repo / ".gitignore"
    existing = gitignore_path.read_text(encoding="utf-8").splitlines() if gitignore_path.exists() else []
    existing_stripped = [line.strip() for line in existing]
    desired_lines: list[str] = []
    if not claude_dir_preexisted and CLAUDE_DIR_GITIGNORE_LINE not in existing_stripped:
        desired_lines.append(CLAUDE_DIR_GITIGNORE_LINE)
    if not claude_md_preexisted and CLAUDE_MD_GITIGNORE_LINE not in existing_stripped:
        desired_lines.append(CLAUDE_MD_GITIGNORE_LINE)
    if not desired_lines:
        return None
    if existing and existing[-1].strip():
        existing.append("")
    existing.append(CLAUDE_GITIGNORE_COMMENT)
    existing.extend(desired_lines)
    gitignore_path.write_text("\n".join(existing).rstrip() + "\n", encoding="utf-8")
    return gitignore_path


def render_session_start_script() -> str:
    return """#!/usr/bin/env python3
import json

summary = [
    "AICTX runtime loaded for this Claude session.",
    "MCP-first startup: if AICTX MCP tools are already visible, use those tools; if not visible but .mcp.json or .vscode/mcp.json exists, first use runner tool discovery when available (search for aictx resume finalize lifecycle), then have Claude Code attach/start the configured stdio MCP server before the first AICTX command of the new session; use CLI fallback only if MCP tools still are not attached after discovery/attachment.",
    "Lifecycle remains prepare/startup context → resume capsule → work → finalize → final AICTX summary/persistence.",
    "At prompt start, use one continuity command: aictx resume --repo . --task \\\"<task goal>\\\" --json.",
    "Use the returned capsule as the operational brief.",
    "Render exactly one startup banner source: normal agent startup uses resume.startup_banner_text or resume.startup_banner_render_payload; wrapped execution uses prepare_execution().startup_banner_text or prepare_execution().startup_banner_render_payload. Do not render both.",
    "resume does not replace prepare_execution, finalize_execution, the startup banner, the final AICTX summary, or persistence.",
    "Do not inspect .aictx/ or run exploratory AICTX commands during normal startup.",
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
import sys


payload = json.load(sys.stdin)
prompt = str(payload.get("prompt") or "").strip()
if not prompt:
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": "AICTX: empty prompt"}}))
    raise SystemExit(0)

summary = [
    "AICTX runtime guidance loaded for this prompt.",
    "MCP-first startup: if AICTX MCP tools are already visible, use those tools; if not visible but .mcp.json or .vscode/mcp.json exists, first use runner tool discovery when available (search for aictx resume finalize lifecycle), then have Claude Code attach/start the configured stdio MCP server before the first AICTX command of the new session; use CLI fallback only if MCP tools still are not attached after discovery/attachment.",
    "Lifecycle remains prepare/startup context → resume capsule → work → finalize → final AICTX summary/persistence.",
    "Extract the task goal only from the user prompt.",
    "Run exactly one continuity command: aictx resume --repo . --task \\\"<task goal>\\\" --json --agent-id claude.",
    "Do not pass the full user prompt to resume.",
    "Exclude reporting instructions, metrics schemas, output format rules, final answer format, benchmark/evaluation harness text, logging instructions, and meta-instructions about how to report the work.",
    "Use the returned aictx resume continuity capsule before broad repo scanning.",
    "Render exactly one startup banner source: normal agent startup uses resume.startup_banner_text or resume.startup_banner_render_payload; wrapped execution uses prepare_execution().startup_banner_text or prepare_execution().startup_banner_render_payload. Do not render both.",
    "resume does not replace prepare_execution, finalize_execution, the startup banner, the final AICTX summary, or persistence.",
]
summary.append("Do not inspect .aictx/ during normal startup.")
summary.append("Do not run exploratory AICTX commands during normal startup.")
summary.append("Do not run aictx internal, aictx -h, aictx reuse, aictx suggest, aictx next, aictx task, aictx messages, aictx reflect, or aictx report during normal startup unless diagnostics, AICTX-internal work, corrupt resume, or finalization/update lifecycle requires it.")
summary.append("In the aictx source repository, prefer: PYTHONPATH=src .venv/bin/python -m aictx ...")
summary.append("Render exactly one startup banner source. Normal agent startup uses resume.startup_banner_text or resume.startup_banner_render_payload. Wrapped execution uses prepare_execution().startup_banner_text or prepare_execution().startup_banner_render_payload. Do not render both. On the first execution of each visible session, place the selected startup banner at the start of the first substantive user-visible response in the current user language; do not consume it with a transient progress/status message that will be omitted from the final task response. If first-session text is missing, render {agent_label} · session #{session_count} · awake from selected identity fields. Do not render it again after already_shown is true.")
summary.append("After finalize, append the AICTX final summary to the final user response, localized to the current user language while preserving factual runtime content.")
summary.append("When available, follow prepared.runtime_text_policy, prepared.startup_banner_policy, and finalized.agent_summary_policy. If render_payload_field points to startup_banner_render_payload or agent_summary_render_payload, prefer those structured payloads for localization and use compact text fields only as fallback while preserving exact facts, technical tokens, and the details/continuity link targets. Render every provided summary section, including `details`, `continuity_view_file`, and `continuity_view_online`; do not replace Mermaid URLs with placeholders and do not manually reconstruct or retype pako URLs.")
summary.append("If no finalize output exists, say: AICTX summary unavailable.")

print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "UserPromptSubmit",
        "additionalContext": "\\n".join(summary)
    }
}))
"""


def render_claude_pre_tool_use_script() -> str:
    generated_prefixes = [f"{name}/" for name in sorted(GENERATED_RUNTIME_DIRS)]
    return """#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path


GENERATED_PREFIXES = [
""" + "\n".join(f'    "{prefix}",' for prefix in generated_prefixes) + """
]
EDITABLE_SOURCE_PREFIXES = [
    ".aictx/memory/source/",
]
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
    if any(rel_path == prefix.rstrip("/") or rel_path.startswith(prefix) for prefix in EDITABLE_SOURCE_PREFIXES):
        return False
    if any(rel_path == prefix.rstrip("/") or rel_path.startswith(prefix) for prefix in GENERATED_PREFIXES):
        return True
    return False


payload = json.load(sys.stdin)
repo_root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()).resolve()
tool_name = str(payload.get("tool_name") or "")
tool_input = payload.get("tool_input", {}) if isinstance(payload.get("tool_input"), dict) else {}

if tool_name in WRITE_TOOL_NAMES:
    file_path = str(tool_input.get("file_path") or "")
    rel_path = normalize_rel(file_path, repo_root)
    if path_is_blocked(rel_path):
        deny(
            "AICTX policy: generated runtime artifacts must not be edited directly. "
            "Edit durable notes in .aictx/memory/source/ instead and let aictx regenerate derived state."
        )

if tool_name == "Bash":
    command = str(tool_input.get("command") or "")
    lowered = command.lower()
    risky_tokens = ["rm ", "mv ", "cp ", "sed ", "perl ", "python ", "python3 ", "cat >", "> ", ">> ", "tee "]
    mentions_generated = any(prefix in command for prefix in GENERATED_PREFIXES) or any(prefix.rstrip("/") in command for prefix in GENERATED_PREFIXES)
    if mentions_generated and any(token in lowered for token in risky_tokens):
        deny(
            "AICTX policy: do not mutate generated runtime artifacts from Bash. "
            "Use aictx-owned flows instead."
        )

raise SystemExit(0)
"""


def ensure_codex_config_hardening() -> list[Path]:
    CODEX_HOME.mkdir(parents=True, exist_ok=True)
    instructions_path = codex_instructions_path()
    existing = CODEX_CONFIG_PATH.read_text(encoding="utf-8") if CODEX_CONFIG_PATH.exists() else ""
    managed_comment = "# AICTX managed fallback docs for stronger repo instruction loading"
    desired = 'project_doc_fallback_filenames = ["CLAUDE.md"]'
    instructions_comment = "# AICTX managed mandatory Codex developer instructions"
    instructions_line = f'model_instructions_file = "{instructions_path.as_posix()}"'
    existing_without_legacy = strip_legacy_codex_mcp_block(existing)
    changed = existing_without_legacy != existing
    existing = existing_without_legacy
    updated = existing.rstrip()
    if "project_doc_fallback_filenames" not in existing:
        if updated:
            updated += "\n\n"
        updated += managed_comment + "\n" + desired
        changed = True
    if "model_instructions_file" not in existing:
        if updated:
            updated += "\n\n"
        updated += instructions_comment + "\n" + instructions_line
        changed = True
    if AICTX_CONFIG_START not in existing and "[mcp_servers.aictx]" not in existing and '[mcp_servers."aictx"]' not in existing:
        if updated:
            updated += "\n\n"
        updated += render_codex_mcp_config_block()
        changed = True
    if changed:
        CODEX_CONFIG_PATH.write_text(updated.rstrip() + "\n", encoding="utf-8")
    return [CODEX_CONFIG_PATH]


def strip_legacy_codex_mcp_block(text: str) -> str:
    lines = text.splitlines()
    output: list[str] = []
    changed = False
    index = 0
    while index < len(lines):
        stripped = lines[index].strip()
        if stripped in {"[mcp_servers.aictx]", '[mcp_servers."aictx"]'}:
            end = index + 1
            while end < len(lines) and not lines[end].lstrip().startswith("["):
                end += 1
            block_text = "\n".join(lines[index:end])
            if 'command = "aictx"' in block_text and "mcp-server" in block_text:
                changed = True
                index = end
                while output and not output[-1].strip():
                    output.pop()
                while index < len(lines) and not lines[index].strip():
                    index += 1
                continue
        output.append(lines[index])
        index += 1
    return ("\n".join(output).rstrip() + "\n") if changed and output else "" if changed else text


def install_codex_native_integration() -> list[Path]:
    instructions_path = codex_instructions_path()
    write_executable(instructions_path, render_codex_global_instructions())
    path = CODEX_HOME / "AGENTS.override.md"
    upsert_marked_block(path, render_codex_home_block())
    created = [instructions_path, path]
    created.extend(ensure_codex_config_hardening())
    return created


def install_copilot_repo_integration(repo: Path) -> list[Path]:
    path = repo / COPILOT_INSTRUCTIONS_PATH
    upsert_marked_block(path, render_copilot_instructions_block())
    path_instructions = repo / COPILOT_PATH_INSTRUCTIONS_PATH
    upsert_copilot_path_instructions(path_instructions)
    resume_prompt = repo / COPILOT_RESUME_PROMPT_PATH
    upsert_marked_block(resume_prompt, render_copilot_resume_prompt())
    finalize_prompt = repo / COPILOT_FINALIZE_PROMPT_PATH
    upsert_marked_block(finalize_prompt, render_copilot_finalize_prompt())
    return [path, path_instructions, resume_prompt, finalize_prompt]


def install_repo_runner_integrations(repo: Path) -> list[Path]:
    created: list[Path] = []
    created.extend(install_copilot_repo_integration(repo))
    claude_dir = repo / ".claude"
    claude_dir_preexisted = claude_dir.exists()

    claude_md = repo / "CLAUDE.md"
    claude_md_preexisted = claude_md.exists()
    upsert_marked_block(claude_md, render_claude_md_block())
    created.append(claude_md)

    claude_settings = repo / ".claude" / "settings.json"
    write_merged_claude_settings(claude_settings)
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

    gitignore_path = ensure_gitignore_claude_if_created(
        repo,
        claude_dir_preexisted=claude_dir_preexisted,
        claude_md_preexisted=claude_md_preexisted,
    )
    if gitignore_path:
        created.append(gitignore_path)

    return created

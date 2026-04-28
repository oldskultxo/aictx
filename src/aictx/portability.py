from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PORTABILITY_POLICY_VERSION = 1

AICTX_GITIGNORE_START = "# AICTX:START gitignore"
AICTX_GITIGNORE_END = "# AICTX:END gitignore"
PORTABILITY_MODE_LOCAL_ONLY = "local-only"
PORTABILITY_MODE_PORTABLE = "portable-continuity"

PORTABILITY_STATE_PATH = Path(".aictx/continuity/portability.json")

PORTABLE_CONTINUITY_PATTERNS = [
    ".aictx/tasks/active.json",
    ".aictx/tasks/threads/*.json",
    ".aictx/tasks/threads/*.events.jsonl",
    ".aictx/continuity/portability.json",
    ".aictx/continuity/handoff.json",
    ".aictx/continuity/handoffs.jsonl",
    ".aictx/continuity/decisions.jsonl",
    ".aictx/continuity/semantic_repo.json",
    ".aictx/failure_memory/failure_patterns.jsonl",
    ".aictx/strategy_memory/strategies.jsonl",
    ".aictx/area_memory/areas.json",
    ".aictx/repo_map/config.json",
]

LOCAL_ONLY_PATTERNS = [
    ".aictx/metrics/**",
    ".aictx/continuity/session.json",
    ".aictx/continuity/last_execution_summary.md",
    ".aictx/continuity/continuity_metrics.json",
    ".aictx/continuity/dedupe_report.json",
    ".aictx/continuity/staleness.json",
    ".aictx/repo_map/index.json",
    ".aictx/repo_map/manifest.json",
    ".aictx/repo_map/status.json",
]

LOCAL_ONLY_GITIGNORE_LINES = [
    AICTX_GITIGNORE_START,
    f"# mode: {PORTABILITY_MODE_LOCAL_ONLY}",
    ".aictx/",
    AICTX_GITIGNORE_END,
]

PORTABLE_GITIGNORE_LINES = [
    AICTX_GITIGNORE_START,
    f"# mode: {PORTABILITY_MODE_PORTABLE}",
    "",
    ".aictx/*",
    "!.aictx/",
    "",
    "!.aictx/tasks/",
    ".aictx/tasks/*",
    "!.aictx/tasks/active.json",
    "!.aictx/tasks/threads/",
    ".aictx/tasks/threads/*",
    "!.aictx/tasks/threads/*.json",
    "!.aictx/tasks/threads/*.events.jsonl",
    "",
    "!.aictx/continuity/",
    ".aictx/continuity/*",
    "!.aictx/continuity/portability.json",
    "!.aictx/continuity/handoff.json",
    "!.aictx/continuity/handoffs.jsonl",
    "!.aictx/continuity/decisions.jsonl",
    "!.aictx/continuity/semantic_repo.json",
    "",
    "!.aictx/failure_memory/",
    ".aictx/failure_memory/*",
    "!.aictx/failure_memory/failure_patterns.jsonl",
    "",
    "!.aictx/strategy_memory/",
    ".aictx/strategy_memory/*",
    "!.aictx/strategy_memory/strategies.jsonl",
    "",
    "!.aictx/area_memory/",
    ".aictx/area_memory/*",
    "!.aictx/area_memory/areas.json",
    "",
    "!.aictx/repo_map/",
    ".aictx/repo_map/*",
    "!.aictx/repo_map/config.json",
    "",
    AICTX_GITIGNORE_END,
]


def render_aictx_gitignore_block(*, portable_continuity: bool) -> str:
    lines = PORTABLE_GITIGNORE_LINES if portable_continuity else LOCAL_ONLY_GITIGNORE_LINES
    return "\n".join(lines).rstrip() + "\n"


def strip_aictx_gitignore_block(text: str) -> str:
    if AICTX_GITIGNORE_START not in text or AICTX_GITIGNORE_END not in text:
        return text
    start = text.index(AICTX_GITIGNORE_START)
    end = text.index(AICTX_GITIGNORE_END, start) + len(AICTX_GITIGNORE_END)
    head = text[:start].rstrip()
    tail = text[end:].lstrip("\n")
    pieces = [piece for piece in [head, tail] if piece]
    return ("\n".join(pieces) + ("\n" if pieces else ""))


def remove_legacy_aictx_gitignore_lines(text: str) -> str:
    lines = text.splitlines()
    filtered = [line for line in lines if line.strip() != ".aictx/"]
    if not filtered:
        return ""
    return "\n".join(filtered).rstrip() + "\n"


def detect_portable_continuity_from_gitignore(repo: Path) -> bool | None:
    path = repo / ".gitignore"
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    if AICTX_GITIGNORE_START not in text or AICTX_GITIGNORE_END not in text:
        return None
    start = text.index(AICTX_GITIGNORE_START)
    end = text.index(AICTX_GITIGNORE_END, start)
    block = text[start:end]
    if f"# mode: {PORTABILITY_MODE_PORTABLE}" in block:
        return True
    if f"# mode: {PORTABILITY_MODE_LOCAL_ONLY}" in block:
        return False
    return None


def load_portability_state(repo: Path) -> dict[str, Any]:
    path = repo / PORTABILITY_STATE_PATH
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return payload if isinstance(payload, dict) else {}


def write_portability_state(repo: Path, *, enabled: bool) -> Path:
    path = repo / PORTABILITY_STATE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "version": 1,
        "enabled": enabled,
        "mode": PORTABILITY_MODE_PORTABLE if enabled else PORTABILITY_MODE_LOCAL_ONLY,
        "policy_version": PORTABILITY_POLICY_VERSION,
    }
    if enabled:
        payload["portable_patterns"] = list(PORTABLE_CONTINUITY_PATTERNS)
        payload["local_only_patterns"] = list(LOCAL_ONLY_PATTERNS)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

PORTABILITY_POLICY_VERSION = 2

AICTX_GITIGNORE_START = "# AICTX:START gitignore"
AICTX_GITIGNORE_END = "# AICTX:END gitignore"
AICTX_GITATTRIBUTES_START = "# AICTX:START gitattributes"
AICTX_GITATTRIBUTES_END = "# AICTX:END gitattributes"
PORTABILITY_MODE_LOCAL_ONLY = "local-only"
PORTABILITY_MODE_PORTABLE = "portable-continuity"
PORTABILITY_PROFILE_TEAM_SAFE = "team-safe"

PORTABILITY_STATE_PATH = Path(".aictx/continuity/portability.json")

PORTABLE_CONTINUITY_PATTERNS = [
    ".aictx/tasks/threads/*.json",
    ".aictx/tasks/threads/*.events.jsonl",
    ".aictx/continuity/portability.json",
    ".aictx/continuity/handoffs.jsonl",
    ".aictx/continuity/decisions.jsonl",
    ".aictx/continuity/semantic_repo/*.json",
    ".aictx/failure_memory/failure_patterns.jsonl",
    ".aictx/strategy_memory/strategies.jsonl",
    ".aictx/area_memory/areas/*.json",
    ".aictx/repo_map/config.json",
]

PORTABLE_JSONL_MERGE_PATTERNS = [
    ".aictx/tasks/threads/*.events.jsonl",
    ".aictx/continuity/handoffs.jsonl",
    ".aictx/continuity/decisions.jsonl",
    ".aictx/failure_memory/failure_patterns.jsonl",
    ".aictx/strategy_memory/strategies.jsonl",
]

LOCAL_ONLY_PATTERNS = [
    ".aictx/boot/**",
    ".aictx/cost/**",
    ".aictx/delta/**",
    ".aictx/indexes/**",
    ".aictx/logs/**",
    ".aictx/metrics/**",
    ".aictx/store/**",
    ".aictx/task_memory/**",
    ".aictx/memory_graph/**",
    ".aictx/tasks/active.json",
    ".aictx/continuity/handoff.json",
    ".aictx/continuity/semantic_repo.json",
    ".aictx/area_memory/areas.json",
    ".aictx/failure_memory/failure_index.json",
    ".aictx/failure_memory/index.json",
    ".aictx/failure_memory/failure_memory_status.json",
    ".aictx/continuity/session.json",
    ".aictx/continuity/last_execution_summary.md",
    ".aictx/continuity/continuity_metrics.json",
    ".aictx/continuity/dedupe_report.json",
    ".aictx/continuity/staleness.json",
    ".aictx/continuity/resume_capsule.md",
    ".aictx/continuity/resume_capsule.json",
    ".aictx/repo_map/index.json",
    ".aictx/repo_map/manifest.json",
    ".aictx/repo_map/status.json",
]

PORTABLE_GITATTRIBUTES_LINES = [
    AICTX_GITATTRIBUTES_START,
    f"# profile: {PORTABILITY_PROFILE_TEAM_SAFE}",
    "# Git's built-in union merge driver keeps independently appended JSONL rows.",
    *[f"{pattern} merge=union" for pattern in PORTABLE_JSONL_MERGE_PATTERNS],
    AICTX_GITATTRIBUTES_END,
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
    "!.aictx/tasks/threads/",
    ".aictx/tasks/threads/*",
    "!.aictx/tasks/threads/*.json",
    "!.aictx/tasks/threads/*.events.jsonl",
    "",
    "!.aictx/continuity/",
    ".aictx/continuity/*",
    "!.aictx/continuity/portability.json",
    "!.aictx/continuity/handoffs.jsonl",
    "!.aictx/continuity/decisions.jsonl",
    "!.aictx/continuity/semantic_repo/",
    ".aictx/continuity/semantic_repo/*",
    "!.aictx/continuity/semantic_repo/*.json",
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
    "!.aictx/area_memory/areas/",
    ".aictx/area_memory/areas/*",
    "!.aictx/area_memory/areas/*.json",
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


def render_aictx_gitattributes_block(*, portable_continuity: bool) -> str:
    if not portable_continuity:
        return ""
    return "\n".join(PORTABLE_GITATTRIBUTES_LINES).rstrip() + "\n"


def strip_aictx_gitattributes_block(text: str) -> str:
    if AICTX_GITATTRIBUTES_START not in text or AICTX_GITATTRIBUTES_END not in text:
        return text
    start = text.index(AICTX_GITATTRIBUTES_START)
    end = text.index(AICTX_GITATTRIBUTES_END, start) + len(AICTX_GITATTRIBUTES_END)
    head = text[:start].rstrip()
    tail = text[end:].lstrip("\n")
    pieces = [piece for piece in [head, tail] if piece]
    return ("\n".join(pieces) + ("\n" if pieces else ""))


def remove_unmanaged_aictx_gitignore_lines(text: str) -> str:
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
        payload["profile"] = PORTABILITY_PROFILE_TEAM_SAFE
        payload["portable_patterns"] = list(PORTABLE_CONTINUITY_PATTERNS)
        payload["local_only_patterns"] = list(LOCAL_ONLY_PATTERNS)
        payload["merge_policy"] = {
            "transport": "git",
            "external_tool_required": False,
            "jsonl_merge_driver": "union",
            "portable_jsonl_patterns": list(PORTABLE_JSONL_MERGE_PATTERNS),
            "managed_gitattributes": ".gitattributes",
        }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


PORTABLE_JSONL_LIMITS = {
    ".aictx/tasks/threads/*.events.jsonl": 500,
    ".aictx/continuity/handoffs.jsonl": 200,
    ".aictx/continuity/decisions.jsonl": 500,
    ".aictx/failure_memory/failure_patterns.jsonl": 500,
    ".aictx/strategy_memory/strategies.jsonl": 500,
}


def _jsonl_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + ("\n" if rows else ""),
        encoding="utf-8",
    )


def _dedupe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        key = json.dumps(row, ensure_ascii=False, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def compact_portable_jsonl(repo: Path, *, apply: bool = False) -> dict[str, Any]:
    root = repo.expanduser().resolve()
    files: list[dict[str, Any]] = []
    total_duplicates = 0
    total_truncated = 0
    for pattern in PORTABLE_JSONL_MERGE_PATTERNS:
        limit = PORTABLE_JSONL_LIMITS.get(pattern, 500)
        for path in sorted(root.glob(pattern)):
            before = _jsonl_rows(path)
            deduped = _dedupe_rows(before)
            truncated = max(0, len(deduped) - limit)
            after = deduped[-limit:] if limit and len(deduped) > limit else deduped
            duplicates = len(before) - len(deduped)
            changed = duplicates > 0 or truncated > 0
            if changed and apply:
                _write_jsonl(path, after)
            total_duplicates += duplicates
            total_truncated += truncated
            files.append({
                "path": path.relative_to(root).as_posix(),
                "rows_before": len(before),
                "rows_after": len(after),
                "duplicates_removed": duplicates,
                "rows_truncated": truncated,
                "changed": changed,
            })
    return {
        "applied": apply,
        "files": files,
        "duplicates_removed": total_duplicates,
        "rows_truncated": total_truncated,
        "changed": any(item["changed"] for item in files),
    }


def portability_status(repo: Path) -> dict[str, Any]:
    root = repo.expanduser().resolve()
    state = load_portability_state(root)
    enabled = bool(state.get("enabled")) if isinstance(state.get("enabled"), bool) else bool(detect_portable_continuity_from_gitignore(root))
    portable_patterns = list(state.get("portable_patterns", PORTABLE_CONTINUITY_PATTERNS)) if isinstance(state, dict) else list(PORTABLE_CONTINUITY_PATTERNS)
    local_only_patterns = list(state.get("local_only_patterns", LOCAL_ONLY_PATTERNS)) if isinstance(state, dict) else list(LOCAL_ONLY_PATTERNS)
    snapshot_paths = [
        ".aictx/tasks/active.json",
        ".aictx/continuity/handoff.json",
        ".aictx/continuity/semantic_repo.json",
        ".aictx/area_memory/areas.json",
    ]
    legacy_snapshot_risks = [pattern for pattern in snapshot_paths if pattern in portable_patterns]
    tracked_snapshot_risks: list[str] = []
    try:
        tracked = subprocess.run(
            ["git", "ls-files", *snapshot_paths],
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
        )
        if tracked.returncode == 0:
            tracked_snapshot_risks = [line.strip() for line in tracked.stdout.splitlines() if line.strip()]
    except OSError:
        tracked_snapshot_risks = []
    return {
        "enabled": enabled,
        "mode": state.get("mode", PORTABILITY_MODE_PORTABLE if enabled else PORTABILITY_MODE_LOCAL_ONLY) if isinstance(state, dict) else "",
        "policy_version": state.get("policy_version") if isinstance(state, dict) else None,
        "profile": state.get("profile", "") if isinstance(state, dict) else "",
        "state_path": PORTABILITY_STATE_PATH.as_posix(),
        "gitattributes_path": ".gitattributes",
        "gitattributes_present": (root / ".gitattributes").exists(),
        "portable_patterns": portable_patterns,
        "local_only_patterns": local_only_patterns,
        "merge_policy": state.get("merge_policy", {}) if isinstance(state, dict) else {},
        "jsonl_compaction": compact_portable_jsonl(root, apply=False),
        "legacy_snapshot_risks": legacy_snapshot_risks,
        "tracked_snapshot_risks": tracked_snapshot_risks,
        "recommendations": [
            "run aictx portability compact --repo . --apply --json" if enabled else "enable with aictx init --portable-continuity",
        ]
        + (["run aictx internal migrate to upgrade portable snapshot policy"] if legacy_snapshot_risks else [])
        + (["untrack local-only snapshots with git rm --cached <path>"] if tracked_snapshot_risks else []),
    }

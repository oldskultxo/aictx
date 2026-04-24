from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .failure_memory import lookup_failures
from .state import (
    REPO_CONTINUITY_DIR,
    REPO_CONTINUITY_SESSION_PATH,
    REPO_MEMORY_DIR,
    read_json,
    read_jsonl,
)
from .strategy_memory import select_strategy

HANDOFF_PATH = REPO_CONTINUITY_DIR / "handoff.json"
DECISIONS_PATH = REPO_CONTINUITY_DIR / "decisions.jsonl"
SEMANTIC_REPO_PATH = REPO_CONTINUITY_DIR / "semantic_repo.json"


def _read_optional_json(repo_root: Path, relative_path: Path, expected_type: type, warnings: list[str]) -> Any:
    path = repo_root / relative_path
    if not path.exists():
        return {} if expected_type is dict else []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        warnings.append(f"malformed:{relative_path.as_posix()}")
        return {} if expected_type is dict else []
    if not isinstance(payload, expected_type):
        warnings.append(f"invalid_type:{relative_path.as_posix()}")
        return {} if expected_type is dict else []
    return payload


def _read_optional_jsonl(repo_root: Path, relative_path: Path, warnings: list[str]) -> list[dict[str, Any]]:
    path = repo_root / relative_path
    if not path.exists():
        return []
    rows = read_jsonl(path)
    invalid_lines = 0
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        warnings.append(f"unreadable:{relative_path.as_posix()}")
        return rows
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            invalid_lines += 1
            continue
        if not isinstance(payload, dict):
            invalid_lines += 1
    if invalid_lines:
        warnings.append(f"invalid_jsonl_lines:{relative_path.as_posix()}:{invalid_lines}")
    return rows


def _session_from_payload(session_identity: dict[str, Any] | None, repo_root: Path, warnings: list[str]) -> dict[str, Any]:
    if isinstance(session_identity, dict):
        session = session_identity.get("session")
        if isinstance(session, dict):
            extra_warnings = session_identity.get("warnings")
            if isinstance(extra_warnings, list):
                warnings.extend(str(item) for item in extra_warnings if str(item).strip())
            return dict(session)
    return _read_optional_json(repo_root, REPO_CONTINUITY_SESSION_PATH, dict, warnings)


def load_continuity_context(
    repo_root: Path,
    *,
    session_identity: dict[str, Any] | None = None,
    task_type: str = "",
    request_text: str = "",
    files: list[str] | None = None,
    primary_entry_point: str | None = None,
    commands: list[str] | None = None,
    tests: list[str] | None = None,
    errors: list[str] | None = None,
    area_id: str = "",
    max_decisions: int = 5,
    max_failures: int = 5,
) -> dict[str, Any]:
    warnings: list[str] = []
    session = _session_from_payload(session_identity, repo_root, warnings)
    preferences = _read_optional_json(repo_root, REPO_MEMORY_DIR / "user_preferences.json", dict, warnings)
    handoff = _read_optional_json(repo_root, HANDOFF_PATH, dict, warnings)
    decisions = _read_optional_jsonl(repo_root, DECISIONS_PATH, warnings)[-max_decisions:]
    semantic_repo = _read_optional_json(repo_root, SEMANTIC_REPO_PATH, dict, warnings)
    failures = lookup_failures(
        repo_root,
        task_type=str(task_type or ""),
        text=str(request_text or ""),
        files=list(files or []),
        area_id=str(area_id or ""),
    )[:max_failures]
    procedural_reuse = select_strategy(
        repo_root,
        str(task_type or "") or None,
        files=list(files or []),
        primary_entry_point=primary_entry_point,
        request_text=request_text,
        commands=list(commands or []),
        tests=list(tests or []),
        errors=list(errors or []),
        area_id=area_id,
    ) or {}
    loaded = {
        "session": bool(session),
        "handoff": bool(handoff),
        "decisions": bool(decisions),
        "failures": bool(failures),
        "preferences": bool(preferences),
        "semantic_repo": bool(semantic_repo),
        "procedural_reuse": bool(procedural_reuse),
    }
    return {
        "agent_identity": session,
        "session": session,
        "loaded": loaded,
        "handoff": handoff,
        "decisions": decisions,
        "failures": failures,
        "semantic_repo": semantic_repo,
        "preferences": preferences,
        "procedural_reuse": procedural_reuse,
        "warnings": warnings,
    }

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ENGINE_HOME = Path.home() / ".aictx"
CONFIG_PATH = ENGINE_HOME / "config.json"
PROJECTS_REGISTRY_PATH = ENGINE_HOME / "projects_registry.json"
WORKSPACES_DIR = ENGINE_HOME / "workspaces"

REPO_ENGINE_DIR = ".aictx"
REPO_COMPAT_DIR = ".aictx/memory"
REPO_MEMORY_DIR = Path(REPO_ENGINE_DIR) / "memory"
REPO_COST_DIR = Path(REPO_ENGINE_DIR) / "cost"
REPO_TASK_MEMORY_DIR = Path(REPO_ENGINE_DIR) / "task_memory"
REPO_FAILURE_MEMORY_DIR = Path(REPO_ENGINE_DIR) / "failure_memory"
REPO_AREA_MEMORY_DIR = Path(REPO_ENGINE_DIR) / "area_memory"
REPO_MEMORY_GRAPH_DIR = Path(REPO_ENGINE_DIR) / "memory_graph"
REPO_STRATEGY_MEMORY_DIR = Path(REPO_ENGINE_DIR) / "strategy_memory"
REPO_METRICS_DIR = Path(REPO_ENGINE_DIR) / "metrics"
REPO_ADAPTERS_DIR = Path(REPO_ENGINE_DIR) / "adapters"
REPO_CONTINUITY_DIR = Path(REPO_ENGINE_DIR) / "continuity"
REPO_STATE_PATH = Path(REPO_ENGINE_DIR) / "state.json"
REPO_CONTINUITY_SESSION_PATH = REPO_CONTINUITY_DIR / "session.json"
LEGACY_REPO_DIRS = [
    ".aictx_memory",
    ".aictx_cost",
    ".aictx_task_memory",
    ".aictx_failure_memory",
    ".aictx_memory_graph",
    ".aictx_library",
    ".context_metrics",
]

REPO_DIRS = [
    REPO_ENGINE_DIR,
    REPO_MEMORY_DIR.as_posix(),
    REPO_STRATEGY_MEMORY_DIR.as_posix(),
    REPO_METRICS_DIR.as_posix(),
    REPO_CONTINUITY_DIR.as_posix(),
]

TASK_TYPES = [
    "bug_fixing",
    "refactoring",
    "testing",
    "performance",
    "architecture",
    "feature_work",
    "unknown",
]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    rows: list[dict[str, Any]] = []
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


@dataclass
class Workspace:
    workspace_id: str
    roots: list[str]
    repos: list[str]
    cross_project_mode: str = "workspace"

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": 1,
            "workspace_id": self.workspace_id,
            "roots": self.roots,
            "repos": self.repos,
            "cross_project_mode": self.cross_project_mode,
        }


def default_global_config() -> dict[str, Any]:
    return {
        "version": 1,
        "engine_home": str(ENGINE_HOME),
        "active_workspace": "default",
        "cross_project_mode": "workspace",
    }


def ensure_global_home() -> None:
    ENGINE_HOME.mkdir(parents=True, exist_ok=True)
    WORKSPACES_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists():
        write_json(CONFIG_PATH, default_global_config())
    if not PROJECTS_REGISTRY_PATH.exists():
        write_json(PROJECTS_REGISTRY_PATH, {"version": 1, "projects": []})


def workspace_path(workspace_id: str) -> Path:
    return WORKSPACES_DIR / f"{workspace_id}.json"


def load_active_workspace() -> Workspace:
    ensure_global_home()
    config = read_json(CONFIG_PATH, default_global_config())
    wid = config.get("active_workspace", "default")
    payload = read_json(workspace_path(wid), None)
    if payload is None:
        ws = Workspace(workspace_id=wid, roots=[], repos=[])
        write_json(workspace_path(wid), ws.to_dict())
        return ws
    return Workspace(
        workspace_id=payload.get("workspace_id", wid),
        roots=list(payload.get("roots", [])),
        repos=list(payload.get("repos", [])),
        cross_project_mode=payload.get("cross_project_mode", "workspace"),
    )


def save_workspace(workspace: Workspace) -> None:
    ensure_global_home()
    write_json(workspace_path(workspace.workspace_id), workspace.to_dict())


def _stable_runtime_label(value: str) -> str:
    lowered = str(value or "").strip().lower()
    cleaned = "".join(ch if ch.isalnum() else "-" for ch in lowered).strip("-")
    return cleaned or "generic"


def derive_repo_id(repo_root: Path) -> str:
    payload = read_json(repo_root / REPO_STATE_PATH, {})
    for candidate in (payload.get("repo_id"), repo_root.name, payload.get("project"), payload.get("engine_name")):
        text = str(candidate or "").strip()
        if text:
            return text
    return repo_root.name or "repo"


def derive_runtime(agent_id: str = "", adapter_id: str = "") -> str:
    return _stable_runtime_label(adapter_id or agent_id or "generic")


def derive_visible_session_id(agent_id: str = "", adapter_id: str = "", session_id: str = "") -> str:
    explicit = str(session_id or "").strip()
    if explicit:
        return explicit
    for env_key in ("AICTX_SESSION_ID", "CODEX_SESSION_ID", "CLAUDE_SESSION_ID", "TERM_SESSION_ID"):
        env_value = str(os.environ.get(env_key, "") or "").strip()
        if env_value:
            return env_value
    return f"{derive_runtime(agent_id=agent_id, adapter_id=adapter_id)}:default"


def touch_session_identity(repo_root: Path, agent_id: str = "", adapter_id: str = "", timestamp: str = "", session_id: str = "") -> dict[str, Any]:
    runtime = derive_runtime(agent_id=agent_id, adapter_id=adapter_id)
    repo_id = derive_repo_id(repo_root)
    visible_session_id = derive_visible_session_id(agent_id=agent_id, adapter_id=adapter_id, session_id=session_id)
    session_path = repo_root / REPO_CONTINUITY_SESSION_PATH
    warnings: list[str] = []
    current: dict[str, Any] = {}
    if session_path.exists():
        try:
            payload = json.loads(session_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                current = payload
            else:
                warnings.append("continuity_session_invalid_payload")
        except (json.JSONDecodeError, OSError):
            warnings.append("continuity_session_malformed")
    try:
        previous_count = int(current.get("session_count") or 0)
    except (TypeError, ValueError):
        previous_count = 0
    previous_session_id = str(current.get("session_id") or "").strip()
    is_new_visible_session = not previous_session_id or previous_session_id != visible_session_id
    count = previous_count + 1 if is_new_visible_session and previous_count >= 1 else (previous_count or 1)
    if count < 1:
        count = 1
    event_at = str(timestamp or "").strip() or current.get("last_execution_at") or current.get("last_session_at") or ""
    started_at = event_at if is_new_visible_session else str(current.get("started_at") or current.get("last_session_at") or event_at)
    execution_count = 1
    if not is_new_visible_session:
        try:
            execution_count = int(current.get("execution_count") or 0) + 1
        except (TypeError, ValueError):
            execution_count = 1
    session = {
        "repo_id": repo_id,
        "runtime": runtime,
        "agent_label": f"{runtime}@{repo_id}",
        "session_id": visible_session_id,
        "session_count": count,
        "started_at": started_at,
        "last_session_at": started_at,
        "last_execution_at": event_at,
        "execution_count": execution_count,
        "banner_shown_session_id": "" if is_new_visible_session else str(current.get("banner_shown_session_id") or ""),
        "banner_shown_at": "" if is_new_visible_session else str(current.get("banner_shown_at") or ""),
    }
    write_json(session_path, session)
    return {"session": session, "warnings": warnings, "path": session_path.as_posix()}


def mark_startup_banner_shown(repo_root: Path, session: dict[str, Any], timestamp: str = "") -> dict[str, Any]:
    session_path = repo_root / REPO_CONTINUITY_SESSION_PATH
    current = read_json(session_path, {}) if session_path.exists() else {}
    if not isinstance(current, dict):
        current = {}
    active = dict(current or session)
    session_id = str(active.get("session_id") or session.get("session_id") or "").strip()
    shown_at = str(timestamp or "").strip() or str(active.get("last_execution_at") or active.get("started_at") or "")
    active["banner_shown_session_id"] = session_id
    active["banner_shown_at"] = shown_at
    write_json(session_path, active)
    return active

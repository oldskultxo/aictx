from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ENGINE_HOME = Path.home() / ".ai_context_engine"
CONFIG_PATH = ENGINE_HOME / "config.json"
PROJECTS_REGISTRY_PATH = ENGINE_HOME / "projects_registry.json"
WORKSPACES_DIR = ENGINE_HOME / "workspaces"
GLOBAL_METRICS_DIR = ENGINE_HOME / ".ai_context_global_metrics"

REPO_ENGINE_DIR = ".ai_context_engine"
REPO_COMPAT_DIR = ".ai_context_engine/memory"
REPO_MEMORY_DIR = Path(REPO_ENGINE_DIR) / "memory"
REPO_COST_DIR = Path(REPO_ENGINE_DIR) / "cost"
REPO_TASK_MEMORY_DIR = Path(REPO_ENGINE_DIR) / "task_memory"
REPO_FAILURE_MEMORY_DIR = Path(REPO_ENGINE_DIR) / "failure_memory"
REPO_MEMORY_GRAPH_DIR = Path(REPO_ENGINE_DIR) / "memory_graph"
REPO_LIBRARY_DIR = Path(REPO_ENGINE_DIR) / "library"
REPO_STRATEGY_MEMORY_DIR = Path(REPO_ENGINE_DIR) / "strategy_memory"
REPO_METRICS_DIR = Path(REPO_ENGINE_DIR) / "metrics"
REPO_ADAPTERS_DIR = Path(REPO_ENGINE_DIR) / "adapters"
REPO_STATE_PATH = Path(REPO_ENGINE_DIR) / "state.json"
LEGACY_REPO_DIRS = [
    ".ai_context_memory",
    ".ai_context_cost",
    ".ai_context_task_memory",
    ".ai_context_failure_memory",
    ".ai_context_memory_graph",
    ".ai_context_library",
    ".context_metrics",
]

REPO_DIRS = [
    REPO_ENGINE_DIR,
    REPO_MEMORY_DIR.as_posix(),
    REPO_STRATEGY_MEMORY_DIR.as_posix(),
    REPO_METRICS_DIR.as_posix(),
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
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


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
        "global_metrics_enabled": True,
    }


def ensure_global_home() -> None:
    ENGINE_HOME.mkdir(parents=True, exist_ok=True)
    WORKSPACES_DIR.mkdir(parents=True, exist_ok=True)
    GLOBAL_METRICS_DIR.mkdir(parents=True, exist_ok=True)
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

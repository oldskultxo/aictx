from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .state import REPO_STRATEGY_MEMORY_DIR

STRATEGIES_PATH = REPO_STRATEGY_MEMORY_DIR / "strategies.jsonl"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def strategies_path(repo_root: Path) -> Path:
    return repo_root / STRATEGIES_PATH


def ensure_strategy_memory(repo_root: Path) -> Path:
    path = strategies_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("", encoding="utf-8")
    return path


def load_strategies(repo_root: Path) -> list[dict[str, Any]]:
    return read_jsonl(strategies_path(repo_root))


def get_strategies_by_task_type(repo_root: Path, task_type: str) -> list[dict[str, Any]]:
    target = str(task_type or "unknown")
    return [row for row in load_strategies(repo_root) if str(row.get("task_type") or "unknown") == target]


def build_strategy_entry(prepared: dict[str, Any], execution_log: dict[str, Any], timestamp: str) -> dict[str, Any]:
    files_used = execution_log.get("files_opened", []) if isinstance(execution_log.get("files_opened"), list) else []
    normalized_files = [str(path) for path in files_used if str(path).strip()]
    return {
        "task_id": str(execution_log.get("task_id") or prepared.get("envelope", {}).get("execution_id") or ""),
        "task_type": str(prepared.get("resolved_task_type") or execution_log.get("task_type") or "unknown"),
        "entry_points": normalized_files[:2],
        "files_used": normalized_files,
        "success": True,
        "timestamp": timestamp,
    }


def strategy_exists(repo_root: Path, strategy: dict[str, Any]) -> bool:
    for row in load_strategies(repo_root):
        if str(row.get("task_id") or "") == str(strategy.get("task_id") or ""):
            return True
    return False


def persist_strategy(repo_root: Path, strategy: dict[str, Any]) -> dict[str, Any] | None:
    path = ensure_strategy_memory(repo_root)
    if strategy_exists(repo_root, strategy):
        return None
    append_jsonl(path, strategy)
    return {"path": path.as_posix(), "task_id": strategy.get("task_id", "")}

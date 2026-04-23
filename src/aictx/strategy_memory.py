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


def successful_strategies(repo_root: Path) -> list[dict[str, Any]]:
    return [row for row in load_strategies(repo_root) if not bool(row.get("is_failure")) and bool(row.get("success", True))]


def get_strategies_by_task_type(repo_root: Path, task_type: str, include_failures: bool = False) -> list[dict[str, Any]]:
    target = str(task_type or "unknown")
    rows = [row for row in load_strategies(repo_root) if str(row.get("task_type") or "unknown") == target]
    if include_failures:
        return rows
    return [row for row in rows if not bool(row.get("is_failure"))]


def _list_field(row: dict[str, Any], key: str) -> list[str]:
    value = row.get(key)
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _path_overlap(strategy: dict[str, Any], files: list[str]) -> list[str]:
    targets = {str(path).strip() for path in files if str(path).strip()}
    if not targets:
        return []
    strategy_files = set(_list_field(strategy, "files_used") + _list_field(strategy, "entry_points"))
    return sorted(strategy_files.intersection(targets))


def rank_strategy(
    strategy: dict[str, Any],
    *,
    task_type: str | None = None,
    files: list[str] | None = None,
    primary_entry_point: str | None = None,
    recency_index: int = 0,
) -> dict[str, Any]:
    target_task_type = str(task_type or "").strip()
    target_primary = str(primary_entry_point or "").strip()
    target_files = [str(path) for path in (files or []) if str(path).strip()]
    overlap = _path_overlap(strategy, target_files)
    primary = str(strategy.get("primary_entry_point") or "").strip()
    score = recency_index
    reasons: list[str] = []
    if target_task_type and str(strategy.get("task_type") or "unknown") == target_task_type:
        score += 1000
        reasons.append(f"task_type:{target_task_type}")
    if target_primary and primary == target_primary:
        score += 5000
        reasons.append(f"primary_entry_point:{target_primary}")
    if overlap:
        score += 3000 + len(overlap) * 100
        reasons.append("file_overlap:" + ",".join(overlap[:5]))
    if not reasons:
        reasons.append("recency")
    return {
        "score": score,
        "selection_reason": "; ".join(reasons),
        "matched_signals": reasons,
        "overlapping_files": overlap,
    }


def select_strategy(
    repo_root: Path,
    task_type: str | None = None,
    *,
    files: list[str] | None = None,
    primary_entry_point: str | None = None,
) -> dict[str, Any] | None:
    rows = get_strategies_by_task_type(repo_root, task_type) if task_type else successful_strategies(repo_root)
    if not rows:
        return None
    ranked: list[tuple[int, int, dict[str, Any], dict[str, Any]]] = []
    for index, row in enumerate(rows):
        ranking = rank_strategy(
            row,
            task_type=task_type,
            files=files,
            primary_entry_point=primary_entry_point,
            recency_index=index,
        )
        ranked.append((int(ranking["score"]), index, row, ranking))
    _score, _index, selected, ranking = max(ranked, key=lambda item: (item[0], item[1]))
    enriched = dict(selected)
    enriched["selection_reason"] = ranking["selection_reason"]
    enriched["matched_signals"] = ranking["matched_signals"]
    enriched["overlapping_files"] = ranking["overlapping_files"]
    return enriched


def build_strategy_entry(prepared: dict[str, Any], execution_log: dict[str, Any], timestamp: str, is_failure: bool) -> dict[str, Any]:
    files_used = execution_log.get("files_opened", []) if isinstance(execution_log.get("files_opened"), list) else []
    normalized_files = [str(path) for path in files_used if str(path).strip()]
    primary_entry_point = normalized_files[0] if normalized_files else None
    return {
        "task_id": str(execution_log.get("task_id") or prepared.get("envelope", {}).get("execution_id") or ""),
        "task_type": str(prepared.get("resolved_task_type") or execution_log.get("task_type") or "unknown"),
        "entry_points": normalized_files[:3],
        "primary_entry_point": primary_entry_point,
        "files_used": normalized_files,
        "success": not is_failure,
        "is_failure": is_failure,
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


def latest_strategy(repo_root: Path, task_type: str | None = None) -> dict[str, Any] | None:
    return select_strategy(repo_root, task_type)

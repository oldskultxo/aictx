from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .state import REPO_STRATEGY_MEMORY_DIR, read_jsonl

STRATEGIES_PATH = REPO_STRATEGY_MEMORY_DIR / "strategies.jsonl"


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
    return [row for row in rows if not bool(row.get("is_failure")) and bool(row.get("success", True))]


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


def _tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-zA-Z0-9_]{3,}", str(text).lower())}


def _overlap(left: list[str], right: list[str]) -> list[str]:
    return sorted(set(left).intersection(set(right)))


def _text_similarity(left: str, right: str) -> float:
    a = _tokens(left)
    b = _tokens(right)
    if not a or not b:
        return 0.0
    return round(len(a.intersection(b)) / len(a.union(b)), 4)


def _area_subsystem(area: str) -> str:
    normalized = str(area or "").strip().strip("/")
    if not normalized:
        return ""
    if "/" not in normalized:
        return normalized
    parts = [part for part in normalized.split("/") if part]
    return "/".join(parts[:2]) if len(parts) >= 2 else normalized


def rank_strategy(
    strategy: dict[str, Any],
    *,
    task_type: str | None = None,
    files: list[str] | None = None,
    primary_entry_point: str | None = None,
    request_text: str | None = None,
    commands: list[str] | None = None,
    tests: list[str] | None = None,
    errors: list[str] | None = None,
    area_id: str | None = None,
    recency_index: int = 0,
) -> dict[str, Any]:
    target_task_type = str(task_type or "").strip()
    target_primary = str(primary_entry_point or "").strip()
    target_files = [str(path) for path in (files or []) if str(path).strip()]
    overlap = _path_overlap(strategy, target_files)
    primary = str(strategy.get("primary_entry_point") or "").strip()
    text_similarity = _text_similarity(str(request_text or ""), str(strategy.get("task_text") or strategy.get("task_id") or ""))
    command_overlap = _overlap(_list_field(strategy, "commands_executed"), commands or [])
    test_overlap = _overlap(_list_field(strategy, "tests_executed"), tests or [])
    error_similarity = _text_similarity(" ".join(errors or []), " ".join(_list_field(strategy, "notable_errors")))
    strategy_area = str(strategy.get("area_id") or "")
    target_area = str(area_id or "")
    strategy_subsystem = str(strategy.get("subsystem") or _area_subsystem(strategy_area))
    target_subsystem = _area_subsystem(target_area)
    score = 0
    reasons: list[str] = []
    breakdown: dict[str, Any] = {"recency": recency_index}
    if not bool(strategy.get("is_failure")) and bool(strategy.get("success", True)):
        breakdown["success_status"] = "success"
    if target_task_type and str(strategy.get("task_type") or "unknown") == target_task_type:
        score += 1000
        reasons.append(f"task_type:{target_task_type}")
        breakdown["task_type"] = 1000
    if target_primary and primary == target_primary:
        score += 5000
        reasons.append(f"primary_entry_point:{target_primary}")
        breakdown["primary_entry_point"] = 5000
    if overlap:
        score += 3000 + len(overlap) * 100
        reasons.append("file_overlap:" + ",".join(overlap[:5]))
        breakdown["file_overlap"] = 3000 + len(overlap) * 100
    if text_similarity:
        boost = int(text_similarity * 2500)
        score += boost
        reasons.append(f"prompt_similarity:{text_similarity}")
        breakdown["prompt_similarity"] = boost
    if command_overlap:
        boost = 900 + len(command_overlap) * 100
        score += boost
        reasons.append("command_overlap:" + ",".join(command_overlap[:3]))
        breakdown["command_overlap"] = boost
    if test_overlap:
        boost = 1100 + len(test_overlap) * 100
        score += boost
        reasons.append("test_overlap:" + ",".join(test_overlap[:3]))
        breakdown["test_overlap"] = boost
    if error_similarity:
        boost = int(error_similarity * 1200)
        score += boost
        reasons.append(f"error_similarity:{error_similarity}")
        breakdown["error_similarity"] = boost
    if target_area and strategy_area == target_area:
        score += 800
        reasons.append(f"area:{target_area}")
        breakdown["area"] = 800
    if target_subsystem and strategy_subsystem and strategy_subsystem == target_subsystem and strategy_area != target_area:
        score += 600
        reasons.append(f"subsystem:{target_subsystem}")
        breakdown["subsystem"] = 600
    if not reasons:
        reasons.append("recency")
    breakdown["total"] = score
    return {
        "score": score,
        "selection_reason": "; ".join(reasons),
        "matched_signals": reasons,
        "similarity_breakdown": breakdown,
        "overlapping_files": overlap,
        "related_commands": command_overlap,
        "related_tests": test_overlap,
    }


def select_strategy(
    repo_root: Path,
    task_type: str | None = None,
    *,
    files: list[str] | None = None,
    primary_entry_point: str | None = None,
    request_text: str | None = None,
    commands: list[str] | None = None,
    tests: list[str] | None = None,
    errors: list[str] | None = None,
    area_id: str | None = None,
) -> dict[str, Any] | None:
    rows = get_strategies_by_task_type(repo_root, task_type) if task_type else successful_strategies(repo_root)
    if not rows:
        return None
    ranked: list[tuple[int, int, int, dict[str, Any], dict[str, Any]]] = []
    for index, row in enumerate(rows):
        ranking = rank_strategy(
            row,
            task_type=task_type,
            files=files,
            primary_entry_point=primary_entry_point,
            request_text=request_text,
            commands=commands,
            tests=tests,
            errors=errors,
            area_id=area_id,
            recency_index=index,
        )
        matched_signal_count = len([signal for signal in ranking["matched_signals"] if signal != "recency"])
        ranked.append((int(ranking["score"]), matched_signal_count, index, row, ranking))
    _score, _signal_count, _index, selected, ranking = max(ranked, key=lambda item: (item[0], item[1], item[2]))
    enriched = dict(selected)
    enriched["reused_strategy"] = True
    enriched["score"] = ranking["score"]
    enriched["selection_reason"] = ranking["selection_reason"]
    enriched["matched_signals"] = ranking["matched_signals"]
    enriched["similarity_breakdown"] = ranking["similarity_breakdown"]
    enriched["overlapping_files"] = ranking["overlapping_files"]
    enriched["related_commands"] = ranking["related_commands"]
    enriched["related_tests"] = ranking["related_tests"]
    return enriched


def build_strategy_entry(prepared: dict[str, Any], execution_log: dict[str, Any], timestamp: str, is_failure: bool) -> dict[str, Any]:
    files_used = execution_log.get("files_opened", []) if isinstance(execution_log.get("files_opened"), list) else []
    normalized_files = [str(path) for path in files_used if str(path).strip()]
    primary_entry_point = normalized_files[0] if normalized_files else None
    return {
        "task_id": str(execution_log.get("task_id") or prepared.get("envelope", {}).get("execution_id") or ""),
        "task_text": str(prepared.get("envelope", {}).get("user_request") or ""),
        "task_type": str(prepared.get("resolved_task_type") or execution_log.get("task_type") or "unknown"),
        "area_id": str(execution_log.get("area_id") or prepared.get("area_id") or "unknown"),
        "entry_points": normalized_files[:3],
        "primary_entry_point": primary_entry_point,
        "files_used": normalized_files,
        "files_edited": list(execution_log.get("files_edited", [])) if isinstance(execution_log.get("files_edited"), list) else [],
        "commands_executed": list(execution_log.get("commands_executed", [])) if isinstance(execution_log.get("commands_executed"), list) else [],
        "tests_executed": list(execution_log.get("tests_executed", [])) if isinstance(execution_log.get("tests_executed"), list) else [],
        "notable_errors": list(execution_log.get("notable_errors", [])) if isinstance(execution_log.get("notable_errors"), list) else [],
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

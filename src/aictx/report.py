from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .area_memory import load_area_memory
from .failure_memory import load_failures
from .state import REPO_CONTINUITY_DIR, REPO_METRICS_DIR, REPO_STRATEGY_MEMORY_DIR, read_json, write_json


EXECUTION_LOGS_PATH = REPO_METRICS_DIR / "execution_logs.jsonl"
EXECUTION_FEEDBACK_PATH = REPO_METRICS_DIR / "execution_feedback.jsonl"
STRATEGIES_PATH = REPO_STRATEGY_MEMORY_DIR / "strategies.jsonl"
MEMORY_HYGIENE_PATH = REPO_METRICS_DIR / "memory_hygiene.json"
CONTINUITY_METRICS_PATH = REPO_CONTINUITY_DIR / "continuity_metrics.json"


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


def _average(values: list[int | float]) -> int | None:
    if not values:
        return None
    return int(round(sum(values) / len(values)))


def build_real_usage_report(repo_root: Path) -> dict[str, Any]:
    logs = read_jsonl(repo_root / EXECUTION_LOGS_PATH)
    feedback_rows = read_jsonl(repo_root / EXECUTION_FEEDBACK_PATH)

    execution_times = [
        int(row.get("execution_time_ms"))
        for row in logs
        if isinstance(row.get("execution_time_ms"), int)
    ]
    files_opened = [
        len(row.get("files_opened", []))
        for row in logs
        if isinstance(row.get("files_opened"), list)
    ]
    reopened_files = [
        len(row.get("files_reopened", []))
        for row in logs
        if isinstance(row.get("files_reopened"), list)
    ]

    strategy_usage = 0
    packet_usage = 0
    redundant_exploration = 0
    summaries_available = 0
    for row in feedback_rows:
        feedback = row.get("aictx_feedback", {}) if isinstance(row.get("aictx_feedback"), dict) else {}
        if bool(feedback.get("used_strategy")):
            strategy_usage += 1
        if bool(feedback.get("used_packet")):
            packet_usage += 1
        if bool(feedback.get("possible_redundant_exploration")):
            redundant_exploration += 1
        if row.get("agent_summary"):
            summaries_available += 1

    capture_fields = ["files_opened", "files_edited", "commands_executed", "tests_executed", "notable_errors"]
    capture_coverage = {
        field: sum(1 for row in logs if isinstance(row.get(field), list) and bool(row.get(field)))
        for field in capture_fields
    }
    area_memory = load_area_memory(repo_root)
    failure_count = len(load_failures(repo_root))
    hygiene = build_memory_hygiene_report(repo_root)
    continuity_metrics = read_json(repo_root / CONTINUITY_METRICS_PATH, {})

    return {
        "total_executions": len(logs),
        "avg_execution_time_ms": _average(execution_times),
        "avg_files_opened": _average(files_opened),
        "avg_reopened_files": _average(reopened_files),
        "strategy_usage": strategy_usage,
        "strategy_reuse_rate": round(strategy_usage / len(feedback_rows), 4) if feedback_rows else 0,
        "packet_usage": packet_usage,
        "redundant_exploration_cases": redundant_exploration,
        "capture_coverage": capture_coverage,
        "failure_pattern_count": failure_count,
        "area_count": len(area_memory.get("areas", {})) if isinstance(area_memory.get("areas"), dict) else 0,
        "agent_summaries": summaries_available,
        "memory_hygiene": hygiene,
        "continuity_metrics": continuity_metrics if isinstance(continuity_metrics, dict) else {},
    }


def build_memory_hygiene_report(repo_root: Path) -> dict[str, Any]:
    strategies = read_jsonl(repo_root / STRATEGIES_PATH)
    failures = load_failures(repo_root)
    seen_strategies: set[tuple[Any, ...]] = set()
    duplicate_strategies = 0
    for row in strategies:
        key = (
            row.get("task_type"),
            tuple(row.get("files_used", []) if isinstance(row.get("files_used"), list) else []),
            tuple(row.get("commands_executed", []) if isinstance(row.get("commands_executed"), list) else []),
        )
        if key in seen_strategies:
            duplicate_strategies += 1
        seen_strategies.add(key)
    seen_failures: set[str] = set()
    duplicate_failures = 0
    for row in failures:
        signature = str(row.get("signature") or "")
        if signature and signature in seen_failures:
            duplicate_failures += 1
        seen_failures.add(signature)
    stale_strategies = max(0, len(strategies) - 50)
    payload = {
        "stale_strategy_candidates": stale_strategies,
        "duplicate_strategy_candidates": duplicate_strategies,
        "duplicate_failure_candidates": duplicate_failures,
        "destructive_cleanup_performed": False,
    }
    write_json(repo_root / MEMORY_HYGIENE_PATH, payload)
    return payload

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .state import REPO_METRICS_DIR


EXECUTION_LOGS_PATH = REPO_METRICS_DIR / "execution_logs.jsonl"
EXECUTION_FEEDBACK_PATH = REPO_METRICS_DIR / "execution_feedback.jsonl"


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
    for row in feedback_rows:
        feedback = row.get("aictx_feedback", {}) if isinstance(row.get("aictx_feedback"), dict) else {}
        if bool(feedback.get("used_strategy")):
            strategy_usage += 1
        if bool(feedback.get("used_packet")):
            packet_usage += 1
        if bool(feedback.get("possible_redundant_exploration")):
            redundant_exploration += 1

    return {
        "total_executions": len(logs),
        "avg_execution_time_ms": _average(execution_times),
        "avg_files_opened": _average(files_opened),
        "avg_reopened_files": _average(reopened_files),
        "strategy_usage": strategy_usage,
        "packet_usage": packet_usage,
        "redundant_exploration_cases": redundant_exploration,
    }

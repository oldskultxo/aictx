from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .area_memory import load_area_memory
from .failure_memory import load_failures
from .state import REPO_CONTINUITY_DIR, REPO_MAP_CONFIG_PATH, REPO_MAP_MANIFEST_PATH, REPO_MAP_STATUS_PATH, REPO_METRICS_DIR, REPO_STRATEGY_MEMORY_DIR, read_json, write_json
from .work_state import list_work_states, load_active_work_state, work_state_paths


EXECUTION_LOGS_PATH = REPO_METRICS_DIR / "execution_logs.jsonl"
EXECUTION_FEEDBACK_PATH = REPO_METRICS_DIR / "execution_feedback.jsonl"
STRATEGIES_PATH = REPO_STRATEGY_MEMORY_DIR / "strategies.jsonl"
MEMORY_HYGIENE_PATH = REPO_METRICS_DIR / "memory_hygiene.json"
CONTINUITY_METRICS_PATH = REPO_CONTINUITY_DIR / "continuity_metrics.json"
HANDOFF_PATH = REPO_CONTINUITY_DIR / "handoff.json"
STALENESS_PATH = REPO_CONTINUITY_DIR / "staleness.json"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
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

    capture_fields = ["files_opened", "files_edited", "commands_executed", "tests_executed", "notable_errors", "error_events"]
    capture_coverage = {
        field: sum(1 for row in logs if isinstance(row.get(field), list) and bool(row.get(field)))
        for field in capture_fields
    }
    area_memory = load_area_memory(repo_root)
    failures = load_failures(repo_root)
    failure_count = len(failures)
    open_failures = [row for row in failures if row.get("status") != "resolved"]
    resolved_failures = [row for row in failures if row.get("status") == "resolved"]
    failed_logs = [row for row in logs if row.get("success") is False]
    failure_execution_ids = {str(row.get("last_execution_id") or "") for row in failures if str(row.get("last_execution_id") or "")}
    failed_with_pattern = sum(1 for row in failed_logs if str(row.get("task_id") or "") in failure_execution_ids)
    notable_error_rows = [row for row in logs if isinstance(row.get("notable_errors"), list) and bool(row.get("notable_errors"))]
    notable_error_count = sum(len(row.get("notable_errors", [])) for row in notable_error_rows)
    error_event_rows = [row for row in logs if isinstance(row.get("error_events"), list) and bool(row.get("error_events"))]
    error_events = [event for row in error_event_rows for event in row.get("error_events", []) if isinstance(event, dict)]
    toolchains = sorted({str(event.get("toolchain") or "unknown") for event in error_events if event.get("toolchain")})
    phase_counts: dict[str, int] = {}
    toolchain_counts: dict[str, int] = {}
    for event in error_events:
        toolchain = str(event.get("toolchain") or "unknown")
        phase = str(event.get("phase") or "runtime")
        toolchain_counts[toolchain] = toolchain_counts.get(toolchain, 0) + 1
        phase_counts[phase] = phase_counts.get(phase, 0) + 1
    structured_failure_count = sum(1 for row in failures if isinstance(row.get("error_events"), list) and bool(row.get("error_events")))
    hygiene = build_memory_hygiene_report(repo_root)
    continuity_metrics = read_json(repo_root / CONTINUITY_METRICS_PATH, {})
    continuity_health = build_continuity_health_report(
        repo_root,
        logs=logs,
        feedback_rows=feedback_rows,
        continuity_metrics=continuity_metrics if isinstance(continuity_metrics, dict) else {},
        redundant_exploration=redundant_exploration,
    )
    repo_map = build_repo_map_report(repo_root)
    work_state = build_work_state_report(repo_root)

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
        "error_capture": {
            "notable_error_count": notable_error_count,
            "executions_with_notable_errors": len(notable_error_rows),
            "error_event_count": len(error_events),
            "executions_with_error_events": len(error_event_rows),
            "toolchains_seen": toolchains,
            "top_toolchains": dict(sorted(toolchain_counts.items(), key=lambda item: (-item[1], item[0]))[:5]),
            "top_phases": dict(sorted(phase_counts.items(), key=lambda item: (-item[1], item[0]))[:5]),
            "failure_patterns_with_error_events": structured_failure_count,
            "failed_executions": len(failed_logs),
            "failed_executions_with_failure_pattern": failed_with_pattern,
            "failed_executions_without_failure_pattern": max(0, len(failed_logs) - failed_with_pattern),
        },
        "failure_pattern_count": failure_count,
        "failure_patterns": {
            "open": len(open_failures),
            "resolved": len(resolved_failures),
        },
        "area_count": len(area_memory.get("areas", {})) if isinstance(area_memory.get("areas"), dict) else 0,
        "agent_summaries": summaries_available,
        "memory_hygiene": hygiene,
        "continuity_metrics": continuity_metrics if isinstance(continuity_metrics, dict) else {},
        "continuity_health": continuity_health,
        "repo_map": repo_map,
        "work_state": work_state,
    }


def build_repo_map_report(repo_root: Path) -> dict[str, Any]:
    config = read_json(repo_root / REPO_MAP_CONFIG_PATH, {})
    status = read_json(repo_root / REPO_MAP_STATUS_PATH, {})
    manifest = read_json(repo_root / REPO_MAP_MANIFEST_PATH, {})
    return {
        "enabled": bool((config if isinstance(config, dict) else {}).get("enabled", False)),
        "available": bool((status if isinstance(status, dict) else {}).get("available", False)),
        "files_indexed": int((manifest if isinstance(manifest, dict) else {}).get("files_indexed", 0) or 0),
        "symbols_indexed": int((manifest if isinstance(manifest, dict) else {}).get("symbols_indexed", 0) or 0),
        "last_refresh_status": str((status if isinstance(status, dict) else {}).get("last_refresh_status") or "never"),
    }


def build_work_state_report(repo_root: Path) -> dict[str, Any]:
    active = load_active_work_state(repo_root)
    threads_dir = work_state_paths(repo_root)["threads_dir"]
    threads_count = len(list(threads_dir.glob("*.json"))) if threads_dir.exists() else 0
    recent_statuses: dict[str, int] = {}
    for state in list_work_states(repo_root):
        status = str(state.get("status") or "unknown")
        recent_statuses[status] = recent_statuses.get(status, 0) + 1
    if not active:
        return {
            "active": False,
            "task_id": "",
            "status": "",
            "threads_count": threads_count,
            "last_updated_at": "",
            "recent_statuses": recent_statuses,
        }
    return {
        "active": True,
        "task_id": str(active.get("task_id") or ""),
        "status": str(active.get("status") or ""),
        "threads_count": threads_count,
        "last_updated_at": str(active.get("updated_at") or ""),
        "recent_statuses": recent_statuses,
    }


def build_continuity_health_report(
    repo_root: Path,
    *,
    logs: list[dict[str, Any]],
    feedback_rows: list[dict[str, Any]],
    continuity_metrics: dict[str, Any],
    redundant_exploration: int,
) -> dict[str, Any]:
    total = len(logs)
    packet_usage = 0
    strategy_usage = 0
    for row in feedback_rows:
        feedback = row.get("aictx_feedback", {}) if isinstance(row.get("aictx_feedback"), dict) else {}
        if bool(feedback.get("used_packet")):
            packet_usage += 1
        if bool(feedback.get("used_strategy")):
            strategy_usage += 1
    staleness = read_json(repo_root / STALENESS_PATH, {})
    handoff = read_json(repo_root / HANDOFF_PATH, {})
    stale_excluded = 0
    if isinstance(staleness, dict):
        handoff_state = staleness.get("handoff") if isinstance(staleness.get("handoff"), dict) else {}
        stale_excluded += 1 if handoff_state.get("stale") else 0
        stale_excluded += len(staleness.get("decisions", [])) if isinstance(staleness.get("decisions"), list) else 0
        semantic = staleness.get("semantic_repo") if isinstance(staleness.get("semantic_repo"), dict) else {}
        stale_excluded += len(semantic.get("subsystems", [])) if isinstance(semantic.get("subsystems"), list) else 0
        stale_excluded += len(staleness.get("strategies", [])) if isinstance(staleness.get("strategies"), list) else 0
    capture_quality_rows = []
    for row in feedback_rows:
        summary = row.get("agent_summary") if isinstance(row.get("agent_summary"), dict) else {}
        quality = summary.get("capture_quality") if isinstance(summary.get("capture_quality"), dict) else {}
        if quality:
            capture_quality_rows.append(quality)
    capture_ratios = [
        float(row.get("coverage_ratio"))
        for row in capture_quality_rows
        if isinstance(row.get("coverage_ratio"), (int, float))
    ]
    avg_capture_ratio = round(sum(capture_ratios) / len(capture_ratios), 4) if capture_ratios else None
    unknown_gaps: dict[str, int] = {}
    for row in logs:
        provenance = row.get("capture_provenance") if isinstance(row.get("capture_provenance"), dict) else {}
        for field in ["files_opened", "files_edited", "commands_executed", "tests_executed", "notable_errors"]:
            if str(provenance.get(field) or "unknown") == "unknown":
                unknown_gaps[field] = unknown_gaps.get(field, 0) + 1
    return {
        "packet_context_usefulness": {
            "packet_usage": packet_usage,
            "packet_usage_rate": round(packet_usage / total, 4) if total else 0,
            "strategy_usage_rate": round(strategy_usage / total, 4) if total else 0,
        },
        "stale_memory_excluded": stale_excluded,
        "redundant_exploration_avoided": max(0, int(continuity_metrics.get("strategy_reuse_count", 0) or 0) - redundant_exploration),
        "capture_coverage_gaps": unknown_gaps,
        "avg_capture_quality": avg_capture_ratio,
        "handoff_freshness": {
            "present": bool(handoff),
            "updated_at": str(handoff.get("updated_at") or "") if isinstance(handoff, dict) else "",
            "stale": bool(staleness.get("handoff", {}).get("stale")) if isinstance(staleness.get("handoff"), dict) else False,
        },
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

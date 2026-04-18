from __future__ import annotations

import json
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

MIN_TASKS_ESTIMATED = 20
MIN_TASKS_MEASURED = 60
REQUIRED_BENCHMARK_ARMS = ["A", "B", "C"]


def _cr():
    from . import core_runtime as cr
    return cr


def _benchmark_status_path() -> Path:
    return _cr().CONTEXT_METRICS_DIR / "benchmark_status.json"


def _default_weekly_summary() -> dict[str, Any]:
    return {
        "version": 2,
        "generated_at": date.today().isoformat(),
        "confidence": "low",
        "tasks_sampled": 0,
        "repeated_tasks": 0,
        "phase_events_sampled": 0,
        "telemetry_granularity": "task_plus_phase",
        "estimated_context_reduction": {"range": [0.0, 0.0], "point": 0.0},
        "estimated_total_token_reduction": {"range": [0.0, 0.0]},
        "estimated_latency_improvement": {"range": [0.0, 0.0]},
        "estimated_cost_reduction": {"range": [0.0, 0.0]},
        "top_expensive_phases": [],
        "evidence_status": "insufficient_data",
        "measurement_basis": "fallback_defaults",
        "metrics": {
            "estimated": {
                "context_reduction": {"range": [0.0, 0.0], "point": 0.0},
                "total_token_reduction": {"range": [0.0, 0.0]},
                "latency_improvement": {"range": [0.0, 0.0]},
                "cost_reduction": {"range": [0.0, 0.0]},
            },
            "measured": None,
        },
        "sample_requirements": {
            "min_tasks_for_estimated": MIN_TASKS_ESTIMATED,
            "min_tasks_for_measured": MIN_TASKS_MEASURED,
            "required_benchmark_arms": REQUIRED_BENCHMARK_ARMS,
            "requires_complete_benchmark_for_measured": True,
        },
        "sample_gaps": {
            "tasks_missing_for_estimated": MIN_TASKS_ESTIMATED,
            "tasks_missing_for_measured": MIN_TASKS_MEASURED,
            "benchmark_complete": False,
            "missing_benchmark_arms": REQUIRED_BENCHMARK_ARMS,
        },
    }


def _normalize_legacy_summary(summary: dict[str, Any]) -> dict[str, Any]:
    payload = {**_default_weekly_summary(), **summary}
    estimated_context = payload.get("estimated_context_reduction", {"range": [0.0, 0.0], "point": 0.0})
    estimated_token = payload.get("estimated_total_token_reduction", {"range": [0.0, 0.0]})
    estimated_latency = payload.get("estimated_latency_improvement", {"range": [0.0, 0.0]})
    estimated_cost = payload.get("estimated_cost_reduction", {"range": [0.0, 0.0]})
    metrics = payload.get("metrics", {}) if isinstance(payload.get("metrics"), dict) else {}
    metrics_estimated = metrics.get("estimated", {}) if isinstance(metrics.get("estimated"), dict) else {}
    metrics_estimated = {
        "context_reduction": metrics_estimated.get("context_reduction", estimated_context),
        "total_token_reduction": metrics_estimated.get("total_token_reduction", estimated_token),
        "latency_improvement": metrics_estimated.get("latency_improvement", estimated_latency),
        "cost_reduction": metrics_estimated.get("cost_reduction", estimated_cost),
    }
    payload["metrics"] = {
        "estimated": metrics_estimated,
        "measured": metrics.get("measured"),
    }
    return payload


def load_benchmark_status() -> dict[str, Any]:
    payload = _cr().read_json(
        _benchmark_status_path(),
        {"benchmark_present": False, "complete_abc": False, "arms_covered": []},
    )
    if not isinstance(payload, dict):
        return {"benchmark_present": False, "complete_abc": False, "arms_covered": []}
    arms = sorted({str(arm).upper() for arm in payload.get("arms_covered", []) if str(arm).strip()})
    payload["arms_covered"] = arms
    payload["complete_abc"] = bool(payload.get("complete_abc")) and set(REQUIRED_BENCHMARK_ARMS).issubset(set(arms))
    payload["benchmark_present"] = bool(payload.get("benchmark_present")) or bool(arms)
    return payload


def evidence_status_for(tasks_sampled: int, benchmark_status: dict[str, Any]) -> tuple[str, str]:
    if tasks_sampled < MIN_TASKS_ESTIMATED:
        return "insufficient_data", "fallback_defaults"
    if tasks_sampled >= MIN_TASKS_MEASURED and bool(benchmark_status.get("complete_abc")):
        return "measured", "benchmark_runs"
    return "estimated", "task_logs"


def confidence_for(tasks_sampled: int, evidence_status: str) -> str:
    if evidence_status == "measured":
        return "high"
    if tasks_sampled >= MIN_TASKS_ESTIMATED:
        return "medium"
    return "low"


def apply_truthfulness_guardrails(summary: dict[str, Any]) -> dict[str, Any]:
    payload = _normalize_legacy_summary(summary)
    tasks_sampled = int(payload.get("tasks_sampled", 0) or 0)
    benchmark_status = load_benchmark_status()
    evidence_status, measurement_basis = evidence_status_for(tasks_sampled, benchmark_status)
    confidence = confidence_for(tasks_sampled, evidence_status)

    sample_requirements = payload.get("sample_requirements", {})
    payload["sample_requirements"] = {
        "min_tasks_for_estimated": int(sample_requirements.get("min_tasks_for_estimated", MIN_TASKS_ESTIMATED) or MIN_TASKS_ESTIMATED),
        "min_tasks_for_measured": int(sample_requirements.get("min_tasks_for_measured", MIN_TASKS_MEASURED) or MIN_TASKS_MEASURED),
        "required_benchmark_arms": sample_requirements.get("required_benchmark_arms", REQUIRED_BENCHMARK_ARMS),
        "requires_complete_benchmark_for_measured": bool(sample_requirements.get("requires_complete_benchmark_for_measured", True)),
    }
    missing_arms = sorted(set(REQUIRED_BENCHMARK_ARMS) - set(benchmark_status.get("arms_covered", [])))
    payload["sample_gaps"] = {
        "tasks_missing_for_estimated": max(0, MIN_TASKS_ESTIMATED - tasks_sampled),
        "tasks_missing_for_measured": max(0, MIN_TASKS_MEASURED - tasks_sampled),
        "benchmark_complete": bool(benchmark_status.get("complete_abc")),
        "missing_benchmark_arms": missing_arms,
    }
    payload["evidence_status"] = evidence_status
    payload["measurement_basis"] = measurement_basis
    payload["confidence"] = confidence

    estimated_context = payload.get("estimated_context_reduction", {"range": [0.0, 0.0], "point": 0.0})
    estimated_token = payload.get("estimated_total_token_reduction", {"range": [0.0, 0.0]})
    estimated_latency = payload.get("estimated_latency_improvement", {"range": [0.0, 0.0]})
    estimated_cost = payload.get("estimated_cost_reduction", {"range": [0.0, 0.0]})
    payload["metrics"] = {
        "estimated": {
            "context_reduction": estimated_context,
            "total_token_reduction": estimated_token,
            "latency_improvement": estimated_latency,
            "cost_reduction": estimated_cost,
        },
        "measured": payload.get("metrics", {}).get("measured"),
    }
    if evidence_status != "measured":
        payload["metrics"]["measured"] = None
    return payload


def ensure_context_metrics_artifacts() -> None:
    cr = _cr()
    cr.ensure_dirs()
    if not cr.CONTEXT_TASK_LOGS_PATH.exists():
        cr.write_text(cr.CONTEXT_TASK_LOGS_PATH, '')
    if not cr.CONTEXT_BASELINE_PATH.exists():
        cr.write_json(
            cr.CONTEXT_BASELINE_PATH,
            {
                'version': 1,
                'generated_at': date.today().isoformat(),
                'source': 'derived_from_packets',
                'assumptions': {
                    'average_task_context_tokens_without_engine': 3200,
                    'average_task_context_tokens_with_engine': 1900,
                },
            },
        )
    if not cr.CONTEXT_WEEKLY_SUMMARY_PATH.exists():
        cr.write_json(cr.CONTEXT_WEEKLY_SUMMARY_PATH, _default_weekly_summary())
    if not _benchmark_status_path().exists():
        cr.write_json(
            _benchmark_status_path(),
            {
                "version": 1,
                "generated_at": date.today().isoformat(),
                "benchmark_present": False,
                "complete_abc": False,
                "arms_covered": [],
                "runs_total": 0,
            },
        )


def summarize_granular_telemetry(log_rows: list[dict[str, Any]]) -> dict[str, Any]:
    cr = _cr()
    task_rows = [row for row in log_rows if row.get('level') == 'task']
    phase_rows = [row for row in log_rows if row.get('level') == 'phase']
    if not task_rows:
        return apply_truthfulness_guardrails(cr.read_json(cr.CONTEXT_WEEKLY_SUMMARY_PATH, _default_weekly_summary()))
    context_reductions = [float(row.get('context_reduction_ratio', 0.0) or 0.0) for row in task_rows]
    token_reductions = [float(row.get('token_reduction_estimate', 0.0) or 0.0) for row in task_rows]
    latency_improvements = [float(row.get('latency_reduction_estimate', 0.0) or 0.0) for row in task_rows]
    phase_costs: dict[str, int] = defaultdict(int)
    for row in phase_rows:
        phase_costs[str(row.get('phase_name', 'unknown'))] += int(row.get('estimated_tokens', 0) or 0)
    point = sum(context_reductions) / len(context_reductions)
    token_point = sum(token_reductions) / len(token_reductions)
    latency_point = sum(latency_improvements) / len(latency_improvements)
    summary = {
        'version': 2,
        'generated_at': date.today().isoformat(),
        'confidence': 'medium' if len(task_rows) >= 5 else 'low',
        'tasks_sampled': len(task_rows),
        'repeated_tasks': max(0, len(task_rows) - len({row.get('task_summary') for row in task_rows})),
        'phase_events_sampled': len(phase_rows),
        'telemetry_granularity': 'task_plus_phase',
        'estimated_context_reduction': {'range': [round(max(0.0, point * 0.85), 4), round(min(1.0, point * 1.15), 4)], 'point': round(point, 4)},
        'estimated_total_token_reduction': {'range': [round(max(0.0, token_point * 0.85), 2), round(max(0.0, token_point * 1.15), 2)]},
        'estimated_latency_improvement': {'range': [round(max(0.0, latency_point * 0.85), 2), round(max(0.0, latency_point * 1.15), 2)]},
        'estimated_cost_reduction': {'range': [round(max(0.0, token_point * 0.00001), 4), round(max(0.0, token_point * 0.00002), 4)]},
        'top_expensive_phases': [{'phase_name': name, 'estimated_tokens': tokens} for name, tokens in sorted(phase_costs.items(), key=lambda item: (-item[1], item[0]))[:5]],
    }
    return apply_truthfulness_guardrails(summary)


def record_granular_telemetry(packet: dict[str, Any], packet_path: Path, optimization_report: dict[str, Any]) -> dict[str, Any]:
    cr = _cr()
    ensure_context_metrics_artifacts()
    task_id = str(packet.get('task_id') or cr.slugify(str(packet.get('task_summary', packet.get('task', 'task')))))
    phases = list(packet.get('telemetry_granularity', {}).get('phases', []))
    task_tokens_before = int(optimization_report.get('estimated_tokens_before', 0) or 0)
    task_tokens_after = int(optimization_report.get('estimated_tokens_after', 0) or 0)
    reduction = max(0, task_tokens_before - task_tokens_after)
    task_row = {
        'generated_at': cr.now_iso(),
        'task_id': task_id,
        'level': 'task',
        'task_summary': packet.get('task_summary', packet.get('task')),
        'task_type': packet.get('task_type', 'unknown'),
        'phase_count': len(phases),
        'packet_path': packet_path.as_posix(),
        'estimated_tokens_before': task_tokens_before,
        'estimated_tokens_after': task_tokens_after,
        'token_reduction_estimate': reduction,
        'context_reduction_ratio': round((reduction / task_tokens_before), 4) if task_tokens_before else 0.0,
        'latency_reduction_estimate': round(reduction * 0.002, 4),
    }
    phase_rows = []
    for index, phase in enumerate(phases):
        estimated_tokens = int(phase.get('estimated_tokens', 0) or 0)
        phase_rows.append(
            {
                'generated_at': cr.now_iso(),
                'task_id': task_id,
                'parent_task_id': task_id,
                'level': 'phase',
                'phase_name': phase.get('phase_name', f'phase_{index + 1}'),
                'sequence': index + 1,
                'estimated_tokens': estimated_tokens,
                'notes': phase.get('notes', ''),
            }
        )
    existing = cr.read_jsonl(cr.CONTEXT_TASK_LOGS_PATH)
    cr.write_jsonl(cr.CONTEXT_TASK_LOGS_PATH, (existing + [task_row] + phase_rows)[-400:])
    summary = summarize_granular_telemetry(cr.read_jsonl(cr.CONTEXT_TASK_LOGS_PATH))
    cr.write_json(cr.CONTEXT_WEEKLY_SUMMARY_PATH, summary)
    return summary

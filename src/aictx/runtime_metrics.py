from __future__ import annotations

import json
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any


def _cr():
    from . import core_runtime as cr
    return cr


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
        cr.write_json(
            cr.CONTEXT_WEEKLY_SUMMARY_PATH,
            {
                'version': 2,
                'generated_at': date.today().isoformat(),
                'confidence': 'low',
                'tasks_sampled': 0,
                'repeated_tasks': 0,
                'phase_events_sampled': 0,
                'telemetry_granularity': 'task_plus_phase',
                'estimated_context_reduction': {'range': [0.0, 0.0], 'point': 0.0},
                'estimated_total_token_reduction': {'range': [0.0, 0.0]},
                'estimated_latency_improvement': {'range': [0.0, 0.0]},
                'estimated_cost_reduction': {'range': [0.0, 0.0]},
                'top_expensive_phases': [],
            },
        )


def summarize_granular_telemetry(log_rows: list[dict[str, Any]]) -> dict[str, Any]:
    cr = _cr()
    task_rows = [row for row in log_rows if row.get('level') == 'task']
    phase_rows = [row for row in log_rows if row.get('level') == 'phase']
    if not task_rows:
        return cr.read_json(cr.CONTEXT_WEEKLY_SUMMARY_PATH, {})
    context_reductions = [float(row.get('context_reduction_ratio', 0.0) or 0.0) for row in task_rows]
    token_reductions = [float(row.get('token_reduction_estimate', 0.0) or 0.0) for row in task_rows]
    latency_improvements = [float(row.get('latency_reduction_estimate', 0.0) or 0.0) for row in task_rows]
    phase_costs: dict[str, int] = defaultdict(int)
    for row in phase_rows:
        phase_costs[str(row.get('phase_name', 'unknown'))] += int(row.get('estimated_tokens', 0) or 0)
    point = sum(context_reductions) / len(context_reductions)
    token_point = sum(token_reductions) / len(token_reductions)
    latency_point = sum(latency_improvements) / len(latency_improvements)
    return {
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

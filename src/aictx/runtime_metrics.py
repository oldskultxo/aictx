from __future__ import annotations

from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any


def _cr():
    from . import core_runtime as cr
    return cr


def _default_weekly_summary() -> dict[str, Any]:
    return {
        "version": 3,
        "generated_at": date.today().isoformat(),
        "confidence": "low",
        "tasks_sampled": 0,
        "repeated_tasks": 0,
        "phase_events_sampled": 0,
        "telemetry_granularity": "task_plus_phase",
        "evidence_status": "unknown",
        "measurement_basis": "execution_logs",
        "metrics": {
            "observed": {
                "tasks_sampled": 0,
                "repeated_tasks": 0,
                "phase_events_sampled": 0,
                "top_recorded_phases": [],
            }
        },
    }


def _top_recorded_phases(phase_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts = Counter(str(row.get("phase_name", "unknown")) for row in phase_rows)
    return [
        {"phase_name": name, "events": count}
        for name, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:5]
    ]


def apply_truthfulness_guardrails(summary: dict[str, Any]) -> dict[str, Any]:
    payload = {**_default_weekly_summary(), **summary}
    tasks_sampled = int(payload.get("tasks_sampled", 0) or 0)
    repeated_tasks = int(payload.get("repeated_tasks", 0) or 0)
    phase_events_sampled = int(payload.get("phase_events_sampled", 0) or 0)
    confidence = "medium" if tasks_sampled >= 5 else "low"
    payload["confidence"] = str(payload.get("confidence") or confidence)
    payload["evidence_status"] = "unknown"
    payload["measurement_basis"] = "execution_logs"
    metrics = payload.get("metrics", {}) if isinstance(payload.get("metrics"), dict) else {}
    observed = metrics.get("observed", {}) if isinstance(metrics.get("observed"), dict) else {}
    payload["metrics"] = {
        "observed": {
            "tasks_sampled": tasks_sampled,
            "repeated_tasks": repeated_tasks,
            "phase_events_sampled": phase_events_sampled,
            "top_recorded_phases": list(observed.get("top_recorded_phases", [])),
        }
    }
    return payload


def ensure_context_metrics_artifacts() -> None:
    cr = _cr()
    cr.ensure_dirs()
    if not cr.CONTEXT_TASK_LOGS_PATH.exists():
        cr.write_text(cr.CONTEXT_TASK_LOGS_PATH, "")
    if not cr.CONTEXT_WEEKLY_SUMMARY_PATH.exists():
        cr.write_json(cr.CONTEXT_WEEKLY_SUMMARY_PATH, _default_weekly_summary())


def summarize_granular_telemetry(log_rows: list[dict[str, Any]]) -> dict[str, Any]:
    cr = _cr()
    task_rows = [row for row in log_rows if row.get("level") == "task"]
    phase_rows = [row for row in log_rows if row.get("level") == "phase"]
    if not task_rows:
        return apply_truthfulness_guardrails(cr.read_json(cr.CONTEXT_WEEKLY_SUMMARY_PATH, _default_weekly_summary()))
    summary = {
        "version": 3,
        "generated_at": date.today().isoformat(),
        "confidence": "medium" if len(task_rows) >= 5 else "low",
        "tasks_sampled": len(task_rows),
        "repeated_tasks": max(0, len(task_rows) - len({row.get("task_summary") for row in task_rows})),
        "phase_events_sampled": len(phase_rows),
        "telemetry_granularity": "task_plus_phase",
        "metrics": {
            "observed": {
                "tasks_sampled": len(task_rows),
                "repeated_tasks": max(0, len(task_rows) - len({row.get("task_summary") for row in task_rows})),
                "phase_events_sampled": len(phase_rows),
                "top_recorded_phases": _top_recorded_phases(phase_rows),
            }
        },
    }
    return apply_truthfulness_guardrails(summary)


def record_granular_telemetry(packet: dict[str, Any], packet_path: Path, _optimization_report: dict[str, Any]) -> dict[str, Any]:
    cr = _cr()
    ensure_context_metrics_artifacts()
    task_id = str(packet.get("task_id") or cr.slugify(str(packet.get("task_summary", packet.get("task", "task")))))
    phases = list(packet.get("telemetry_granularity", {}).get("phases", []))
    task_row = {
        "generated_at": cr.now_iso(),
        "task_id": task_id,
        "level": "task",
        "task_summary": packet.get("task_summary", packet.get("task")),
        "task_type": packet.get("task_type", "unknown"),
        "phase_count": len(phases),
        "packet_path": packet_path.as_posix(),
    }
    phase_rows = []
    for index, phase in enumerate(phases):
        phase_rows.append(
            {
                "generated_at": cr.now_iso(),
                "task_id": task_id,
                "parent_task_id": task_id,
                "level": "phase",
                "phase_name": phase.get("phase_name", f"phase_{index + 1}"),
                "sequence": index + 1,
                "notes": phase.get("notes", ""),
            }
        )
    existing = cr.read_jsonl(cr.CONTEXT_TASK_LOGS_PATH)
    cr.write_jsonl(cr.CONTEXT_TASK_LOGS_PATH, (existing + [task_row] + phase_rows)[-400:])
    summary = summarize_granular_telemetry(cr.read_jsonl(cr.CONTEXT_TASK_LOGS_PATH))
    cr.write_json(cr.CONTEXT_WEEKLY_SUMMARY_PATH, summary)
    return summary

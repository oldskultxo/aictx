from __future__ import annotations

from typing import Any


def route_task(task: str) -> dict[str, Any]:
    return {
        "task": task,
        "mode": "deterministic",
    }


def resolve_task_type(
    task: str,
    *,
    explicit_task_type: str | None = None,
    packet_metadata: dict[str, Any] | None = None,
    touched_files: list[str] | None = None,
) -> dict[str, Any]:
    explicit = str(explicit_task_type or "").strip()
    if explicit:
        return {
            "task_type": explicit,
            "source": "explicit_task_type",
            "fallback": False,
            "confidence": 1.0,
            "signals": [f"explicit:{explicit}"],
            "evidence": [f"explicit:{explicit}"],
            "ambiguous": False,
        }
    task_text = str(task or "")
    metadata_type = str((packet_metadata or {}).get("task_type") or "").strip()
    if metadata_type:
        return {
            "task_type": metadata_type,
            "source": "packet_metadata",
            "fallback": False,
            "confidence": 1.0,
            "signals": [f"packet_metadata:{metadata_type}"],
            "evidence": [f"packet_metadata:{metadata_type}"],
            "ambiguous": False,
        }
    files = [str(path) for path in (touched_files or []) if str(path).strip()]
    try:
        from . import core_runtime as cr

        inferred = cr.classify_task_type_from_text(task_text)
        path_signals = cr.infer_task_signals(task_text, files)
        if inferred == "unknown":
            for signal in path_signals:
                parts = signal.split(":", 2)
                if len(parts) >= 2 and parts[0] == "path":
                    inferred = parts[1]
                    break
        confidence = cr.task_type_confidence(task_text, inferred, files)
    except Exception:
        inferred = _fallback_infer_task_type(task_text, files)
        path_signals = _fallback_signals(task_text, files, inferred)
        confidence = 0.35 if inferred == "unknown" else 0.65
    if inferred != "unknown":
        evidence = path_signals or [f"heuristic:{inferred}"]
        return {
            "task_type": inferred,
            "source": "heuristic",
            "fallback": False,
            "confidence": confidence,
            "signals": evidence,
            "evidence": evidence,
            "ambiguous": confidence < 0.55,
        }
    return {
        "task_type": "unknown",
        "source": "unknown_fallback",
        "fallback": True,
        "confidence": confidence,
        "signals": path_signals,
        "evidence": path_signals or ["no_explicit_task_type"],
        "ambiguous": True,
    }


def _fallback_infer_task_type(task: str, files: list[str]) -> str:
    haystack = f"{task} {' '.join(files)}".lower()
    rules = [
        ("architecture", ["architecture", "design", "protocol", "schema"]),
        ("performance", ["performance", "perf", "benchmark", "speed", "latency"]),
        ("testing", ["test", "pytest", "coverage", "assert", "spec"]),
        ("refactoring", ["refactor", "cleanup", "rename", "simplify"]),
        ("bug_fixing", ["bug", "fix", "debug", "failing", "error", "traceback"]),
        ("feature_work", ["feature", "add", "implement", "support"]),
    ]
    for task_type, keywords in rules:
        if any(keyword in haystack for keyword in keywords):
            return task_type
    return "unknown"


def _fallback_signals(task: str, files: list[str], task_type: str) -> list[str]:
    if task_type == "unknown":
        return []
    return [f"heuristic:{task_type}:{task or ','.join(files)}"][:1]


def packet_for_task(
    task: str | dict[str, Any],
    ctx: dict[str, Any] | None = None,
    *,
    project: str | None = None,
    task_type: str | None = None,
) -> dict[str, Any]:
    del project
    if isinstance(task, dict):
        return {
            "task_type": str(task.get("task_type", "unknown") or "unknown"),
            "description": str(task.get("description", "") or ""),
            "context": dict((ctx or {}).get("context", {})) if isinstance(ctx, dict) else {},
        }

    resolved = resolve_task_type(task, explicit_task_type=task_type)
    return {
        "task_type": resolved["task_type"],
        "description": str(task or ""),
        "context": dict((ctx or {}).get("context", {})) if isinstance(ctx, dict) else {},
    }

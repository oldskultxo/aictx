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
    del task, touched_files
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
    return {
        "task_type": "unknown",
        "source": "unknown_fallback",
        "fallback": True,
        "confidence": 0.0,
        "signals": [],
        "evidence": ["no_explicit_task_type"],
        "ambiguous": True,
    }


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

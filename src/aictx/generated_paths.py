from __future__ import annotations

from pathlib import Path

LEGACY_GENERATED_DIRS = {
    ".aictx_memory",
    ".aictx_task_memory",
    ".aictx_failure_memory",
    ".context_metrics",
}

GENERATED_RUNTIME_DIRS = {
    ".aictx",
    *LEGACY_GENERATED_DIRS,
}

EDITABLE_GENERATED_PREFIXES = [
    ".aictx/memory/source/",
]


def is_generated_runtime_path(relative_path: str) -> bool:
    normalized = Path(str(relative_path or "").replace("\\", "/")).as_posix().lstrip("./")
    if not normalized:
        return False
    if any(normalized == prefix.rstrip("/") or normalized.startswith(prefix) for prefix in EDITABLE_GENERATED_PREFIXES):
        return False
    parts = Path(normalized).parts
    return any(part in GENERATED_RUNTIME_DIRS for part in parts)

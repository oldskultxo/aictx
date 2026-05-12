from __future__ import annotations

from pathlib import Path
from typing import Any

from .repo_map.config import is_repomap_enabled
from .repo_map.query import query_repo_map

MAX_STRUCTURAL_ENTRY_POINTS = 5
MAX_STRUCTURAL_SYMBOLS = 5
MAX_STRUCTURAL_REASONS = 5


def _clean_string_list(value: Any, *, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    cleaned: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        cleaned.append(text)
        seen.add(text)
        if len(cleaned) >= limit:
            break
    return cleaned


def _normalize_score(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _entry_id(path: str, title: str) -> str:
    if title:
        return f"{path}::{title}"
    return path


def build_structural_entry_points(
    repo_root: Path,
    request_text: str,
    *,
    files: list[str] | None = None,
    limit: int = MAX_STRUCTURAL_ENTRY_POINTS,
) -> list[dict[str, Any]]:
    """Return compact RepoMap-derived structural entry points for a task.

    This helper is intentionally read-only: it does not refresh RepoMap and it
    never raises to callers. Disabled, missing, stale, or malformed RepoMap
    state simply yields no structural entry points.
    """

    try:
        root = Path(repo_root)
        if not is_repomap_enabled(root):
            return []
        raw_results = query_repo_map(root, request_text, files=files or [], limit=max(1, int(limit or MAX_STRUCTURAL_ENTRY_POINTS)) * 2)
    except Exception:
        return []

    entries: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    for item in raw_results:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or "").strip().replace("\\", "/")
        if not path or path in seen_paths:
            continue
        if not (Path(repo_root) / path).exists():
            continue

        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        symbols = _clean_string_list(item.get("symbols"), limit=MAX_STRUCTURAL_SYMBOLS)
        title = str(item.get("title") or metadata.get("symbol") or (symbols[0] if symbols else path)).strip()
        reasons = _clean_string_list(item.get("reasons"), limit=MAX_STRUCTURAL_REASONS)
        entry = {
            "kind": "structural_entry_point",
            "id": _entry_id(path, title if title != path else ""),
            "path": path,
            "title": title,
            "score": _normalize_score(item.get("score")),
            "reasons": reasons,
            "symbols": symbols,
            "metadata": {
                "symbol": str(metadata.get("symbol") or (symbols[0] if symbols else "")).strip(),
                "symbol_kind": str(metadata.get("symbol_kind") or "").strip(),
                "language": str(metadata.get("language") or "").strip(),
                "line": _normalize_score(metadata.get("line")),
            },
            "source": "repo_map",
        }
        entries.append(entry)
        seen_paths.add(path)
        if len(entries) >= max(0, int(limit or MAX_STRUCTURAL_ENTRY_POINTS)):
            break
    return entries


def structural_context_status(entries: list[dict[str, Any]]) -> dict[str, Any]:
    count = len(entries) if isinstance(entries, list) else 0
    return {
        "enabled": True,
        "available": bool(count),
        "used": bool(count),
        "source": "repo_map",
        "entry_point_count": count,
    }

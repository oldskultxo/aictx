from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from .setup import REPO_MAP_PROVIDER


def file_manifest_entry(repo_root: Path, relative_path: str) -> dict[str, Any] | None:
    path = Path(repo_root) / relative_path
    try:
        stat = path.stat()
    except OSError:
        return None
    if not path.is_file():
        return None
    return {
        "path": str(relative_path),
        "size_bytes": int(stat.st_size),
        "mtime_ns": int(stat.st_mtime_ns),
    }


def file_manifest_entries(repo_root: Path, relative_paths: Iterable[str]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for relative_path in relative_paths:
        entry = file_manifest_entry(repo_root, str(relative_path))
        if entry is not None:
            entries.append(entry)
    return entries


def manifest_entries_by_path(manifest_payload: dict[str, Any], index_payload: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    entries = manifest_payload.get("file_entries", []) if isinstance(manifest_payload, dict) else []
    if isinstance(entries, list) and entries:
        return {
            str(entry.get("path") or ""): {
                "path": str(entry.get("path") or ""),
                "size_bytes": int(entry.get("size_bytes") or 0),
                "mtime_ns": int(entry.get("mtime_ns") or 0),
            }
            for entry in entries
            if isinstance(entry, dict) and str(entry.get("path") or "")
        }

    records = index_payload.get("files", []) if isinstance(index_payload, dict) else []
    if not isinstance(records, list):
        return {}
    return {
        str(record.get("path") or ""): {
            "path": str(record.get("path") or ""),
            "size_bytes": int(record.get("size_bytes") or 0),
            "mtime_ns": int(record.get("mtime_ns") or 0),
        }
        for record in records
        if isinstance(record, dict) and str(record.get("path") or "")
    }


def build_repomap_manifest(
    *,
    files_discovered: int,
    files_indexed: int,
    symbols_indexed: int,
    discovery_source: str,
    ignore_source: str,
    mode: str = "full",
    provider: str = REPO_MAP_PROVIDER,
    file_entries: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "version": 1,
        "provider": provider,
        "mode": mode,
        "discovery_source": discovery_source,
        "ignore_source": ignore_source,
        "files_discovered": files_discovered,
        "files_indexed": files_indexed,
        "symbols_indexed": symbols_indexed,
        "file_entries": list(file_entries or []),
    }

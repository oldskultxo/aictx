from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from .config import (
    load_repomap_index,
    load_repomap_manifest,
    load_repomap_config,
    write_repomap_index,
    write_repomap_manifest,
    write_repomap_status,
)
from .discovery import discover_repo_files
from .index import build_repomap_index, build_repomap_manifest
from .manifest import file_manifest_entries, manifest_entries_by_path
from .provider import check_tree_sitter_available, extract_file_structure
from .setup import REPO_MAP_PROVIDER


def resolve_refresh_mode(requested_mode: str) -> str:
    normalized = str(requested_mode or "full").strip().lower() or "full"
    if normalized == "incremental":
        return "quick"
    return normalized


def refresh_repo_map(
    repo_root: Path,
    *,
    mode: str = "full",
    budget_ms: int | None = None,
    max_changed_files: int | None = None,
) -> dict[str, Any]:
    repo_root = Path(repo_root)
    started = time.perf_counter()
    mode = resolve_refresh_mode(mode)

    if mode == "quick":
        return _quick_refresh_repo_map(
            repo_root,
            started=started,
            budget_ms=budget_ms,
            max_changed_files=max_changed_files,
        )

    if mode != "full":
        return {"status": "unsupported", "reason": "mode_not_implemented", "mode": mode}

    provider_info = check_tree_sitter_available()
    if not provider_info.get("available", False):
        write_repomap_status(
            repo_root,
            {
                "enabled": False,
                "available": False,
                "provider": REPO_MAP_PROVIDER,
                "last_refresh_status": "unavailable",
                "warnings": [str(provider_info.get("error") or "missing_dependency")],
            },
        )
        return {
            "status": "unavailable",
            "reason": str(provider_info.get("error") or "missing_dependency"),
        }

    config = load_repomap_config(repo_root)
    discovery = discover_repo_files(repo_root)
    files = list(discovery.get("files", []))
    records = [
        _extract_record_with_snapshot(repo_root, relative_path, int(config.get("max_parse_file_bytes", 512000)))
        for relative_path in files
    ]
    symbols_indexed = sum(len(record.get("symbols", [])) for record in records if isinstance(record.get("symbols", []), list))

    index_payload = build_repomap_index(
        records=records,
        discovery_source=str(discovery.get("discovery_source") or "scan"),
        ignore_source=str(discovery.get("ignore_source") or "none"),
        mode="full",
    )
    manifest_payload = build_repomap_manifest(
        files_discovered=len(files),
        files_indexed=len(records),
        symbols_indexed=symbols_indexed,
        discovery_source=str(discovery.get("discovery_source") or "scan"),
        ignore_source=str(discovery.get("ignore_source") or "none"),
        mode="full",
        file_entries=file_manifest_entries(repo_root, files),
    )
    write_repomap_index(repo_root, index_payload)
    write_repomap_manifest(repo_root, manifest_payload)
    write_repomap_status(
        repo_root,
        {
            "enabled": bool(config.get("enabled", False)),
            "available": True,
            "provider": REPO_MAP_PROVIDER,
            "last_refresh_mode": "full",
            "last_refresh_status": "ok",
            "last_refresh_ms": int((time.perf_counter() - started) * 1000),
            "warnings": [],
        },
    )

    return {
        "status": "ok",
        "mode": "full",
        "files_discovered": len(files),
        "files_indexed": len(records),
        "symbols_indexed": symbols_indexed,
        "duration_ms": int((time.perf_counter() - started) * 1000),
        "provider": REPO_MAP_PROVIDER,
        "budget_ms": budget_ms,
        "max_changed_files": max_changed_files,
    }


def _quick_refresh_repo_map(
    repo_root: Path,
    *,
    started: float,
    budget_ms: int | None,
    max_changed_files: int | None,
) -> dict[str, Any]:
    config = load_repomap_config(repo_root)
    budget = int(budget_ms if budget_ms is not None else config.get("quick_refresh_budget_ms", 300))
    max_files = int(max_changed_files if max_changed_files is not None else config.get("quick_refresh_max_files", 20))

    index_payload = load_repomap_index(repo_root)
    manifest_payload = load_repomap_manifest(repo_root)
    existing_records = index_payload.get("files", []) if isinstance(index_payload, dict) else []
    if not isinstance(existing_records, list) or not existing_records:
        payload = {
            "enabled": bool(config.get("enabled", False)),
            "available": True,
            "provider": REPO_MAP_PROVIDER,
            "last_refresh_mode": "quick",
            "last_refresh_status": "needs_full_refresh",
            "last_refresh_ms": int((time.perf_counter() - started) * 1000),
            "warnings": ["missing_index"],
        }
        write_repomap_status(repo_root, payload)
        return {
            "status": "needs_full_refresh",
            "mode": "quick",
            "reason": "missing_index",
            "files_reparsed": 0,
            "files_pending": 0,
        }

    provider_info = check_tree_sitter_available()
    if not provider_info.get("available", False):
        payload = {
            "enabled": bool(config.get("enabled", False)),
            "available": False,
            "provider": REPO_MAP_PROVIDER,
            "last_refresh_mode": "quick",
            "last_refresh_status": "skipped",
            "last_refresh_ms": int((time.perf_counter() - started) * 1000),
            "warnings": ["provider_unavailable"],
            "files_reparsed": 0,
        }
        write_repomap_status(repo_root, payload)
        return {
            "status": "skipped",
            "mode": "quick",
            "warnings": ["provider_unavailable"],
            "files_reparsed": 0,
            "files_pending": 0,
        }

    discovery = discover_repo_files(repo_root)
    visible_files = list(discovery.get("files", []))
    current_entries = file_manifest_entries(repo_root, visible_files)
    current_by_path = {str(entry.get("path") or ""): entry for entry in current_entries}
    previous_by_path = manifest_entries_by_path(manifest_payload, index_payload)
    records_by_path = {
        str(record.get("path") or ""): dict(record)
        for record in existing_records
        if isinstance(record, dict) and str(record.get("path") or "")
    }

    changed_paths = [
        path
        for path, current in current_by_path.items()
        if _entry_changed(previous_by_path.get(path), current)
    ]
    changed_paths.sort()
    parsed_paths = changed_paths[: max(0, max_files)]
    pending_paths = changed_paths[len(parsed_paths):]

    new_records: dict[str, dict[str, Any]] = {
        path: record
        for path, record in records_by_path.items()
        if path in current_by_path and path not in changed_paths
    }
    parsed_count = 0
    warnings: list[str] = []
    max_parse_bytes = int(config.get("max_parse_file_bytes", 512000))

    for relative_path in parsed_paths:
        if _budget_exceeded(started, budget):
            if "budget_exceeded" not in warnings:
                warnings.append("budget_exceeded")
            pending_paths.append(relative_path)
            continue
        new_records[relative_path] = _extract_record_with_snapshot(repo_root, relative_path, max_parse_bytes)
        parsed_count += 1

    if _budget_exceeded(started, budget) and "budget_exceeded" not in warnings and pending_paths:
        warnings.append("budget_exceeded")
    if len(changed_paths) > max_files and "max_changed_files_exceeded" not in warnings:
        warnings.append("max_changed_files_exceeded")

    for relative_path in set(pending_paths):
        if relative_path in records_by_path and relative_path in current_by_path and relative_path not in new_records:
            new_records[relative_path] = records_by_path[relative_path]

    pending_set = set(pending_paths)
    final_manifest_entries = [
        previous_by_path[path]
        if path in pending_set and path in previous_by_path
        else entry
        for path, entry in current_by_path.items()
        if path not in pending_set or path in previous_by_path or path in new_records
    ]
    ordered_records = [new_records[path] for path in sorted(new_records)]
    symbols_indexed = _count_symbols(ordered_records)
    status = "partial" if pending_paths or warnings else "ok"
    duration_ms = int((time.perf_counter() - started) * 1000)

    write_repomap_index(
        repo_root,
        build_repomap_index(
            records=ordered_records,
            discovery_source=str(discovery.get("discovery_source") or "scan"),
            ignore_source=str(discovery.get("ignore_source") or "none"),
            mode="quick",
        ),
    )
    write_repomap_manifest(
        repo_root,
        build_repomap_manifest(
            files_discovered=len(visible_files),
            files_indexed=len(ordered_records),
            symbols_indexed=symbols_indexed,
            discovery_source=str(discovery.get("discovery_source") or "scan"),
            ignore_source=str(discovery.get("ignore_source") or "none"),
            mode="quick",
            file_entries=final_manifest_entries,
        ),
    )
    write_repomap_status(
        repo_root,
        {
            "enabled": bool(config.get("enabled", False)),
            "available": True,
            "provider": REPO_MAP_PROVIDER,
            "last_refresh_mode": "quick",
            "last_refresh_status": status,
            "last_refresh_ms": duration_ms,
            "warnings": warnings,
            "files_reparsed": parsed_count,
            "files_pending": len(set(pending_paths)),
        },
    )
    return {
        "status": status,
        "mode": "quick",
        "files_discovered": len(visible_files),
        "files_indexed": len(ordered_records),
        "symbols_indexed": symbols_indexed,
        "files_reparsed": parsed_count,
        "files_pending": len(set(pending_paths)),
        "warnings": warnings,
        "duration_ms": duration_ms,
        "provider": REPO_MAP_PROVIDER,
        "budget_ms": budget,
        "max_changed_files": max_files,
    }


def _extract_record_with_snapshot(repo_root: Path, relative_path: str, max_parse_file_bytes: int) -> dict[str, Any]:
    record = extract_file_structure(repo_root / relative_path, repo_root, max_parse_file_bytes)
    try:
        stat = (repo_root / relative_path).stat()
    except OSError:
        return record
    record["size_bytes"] = int(stat.st_size)
    record["mtime_ns"] = int(stat.st_mtime_ns)
    return record


def _entry_changed(previous: dict[str, Any] | None, current: dict[str, Any]) -> bool:
    if previous is None:
        return True
    return (
        str(previous.get("path") or "") != str(current.get("path") or "")
        or int(previous.get("size_bytes") or 0) != int(current.get("size_bytes") or 0)
        or int(previous.get("mtime_ns") or 0) != int(current.get("mtime_ns") or 0)
    )


def _budget_exceeded(started: float, budget_ms: int) -> bool:
    if budget_ms < 0:
        return False
    return int((time.perf_counter() - started) * 1000) >= budget_ms


def _count_symbols(records: list[dict[str, Any]]) -> int:
    return sum(len(record.get("symbols", [])) for record in records if isinstance(record.get("symbols", []), list))

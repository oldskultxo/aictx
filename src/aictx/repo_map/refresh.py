from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from .config import (
    load_repomap_config,
    write_repomap_index,
    write_repomap_manifest,
    write_repomap_status,
)
from .discovery import discover_repo_files
from .index import build_repomap_index, build_repomap_manifest
from .provider import check_tree_sitter_available, extract_file_structure
from .setup import REPO_MAP_PROVIDER


def refresh_repo_map(
    repo_root: Path,
    *,
    mode: str = "full",
    budget_ms: int | None = None,
    max_changed_files: int | None = None,
) -> dict[str, Any]:
    repo_root = Path(repo_root)
    started = time.perf_counter()

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
        extract_file_structure(repo_root / relative_path, repo_root, int(config.get("max_parse_file_bytes", 512000)))
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
    )
    write_repomap_index(repo_root, index_payload)
    write_repomap_manifest(repo_root, manifest_payload)
    write_repomap_status(
        repo_root,
        {
            "enabled": bool(config.get("enabled", False)),
            "available": True,
            "provider": REPO_MAP_PROVIDER,
            "last_refresh_status": "ok",
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

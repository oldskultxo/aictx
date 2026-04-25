from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .setup import REPO_MAP_PROVIDER


def build_repomap_index(*, records: list[dict[str, Any]], discovery_source: str, ignore_source: str, mode: str = "full", provider: str = REPO_MAP_PROVIDER) -> dict[str, Any]:
    return {
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "provider": provider,
        "mode": mode,
        "discovery_source": discovery_source,
        "ignore_source": ignore_source,
        "files": records,
    }


def build_repomap_manifest(*, files_discovered: int, files_indexed: int, symbols_indexed: int, discovery_source: str, ignore_source: str, mode: str = "full", provider: str = REPO_MAP_PROVIDER) -> dict[str, Any]:
    return {
        "version": 1,
        "provider": provider,
        "mode": mode,
        "discovery_source": discovery_source,
        "ignore_source": ignore_source,
        "files_discovered": files_discovered,
        "files_indexed": files_indexed,
        "symbols_indexed": symbols_indexed,
    }

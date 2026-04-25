from __future__ import annotations

from pathlib import Path

from ..state import (
    REPO_MAP_CONFIG_PATH,
    REPO_MAP_INDEX_PATH,
    REPO_MAP_MANIFEST_PATH,
    REPO_MAP_STATUS_PATH,
)


def repo_map_config_path(repo_root: Path) -> Path:
    return repo_root / REPO_MAP_CONFIG_PATH


def repo_map_manifest_path(repo_root: Path) -> Path:
    return repo_root / REPO_MAP_MANIFEST_PATH


def repo_map_index_path(repo_root: Path) -> Path:
    return repo_root / REPO_MAP_INDEX_PATH


def repo_map_status_path(repo_root: Path) -> Path:
    return repo_root / REPO_MAP_STATUS_PATH

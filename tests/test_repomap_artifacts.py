from __future__ import annotations

import sys
from pathlib import Path

from aictx.repo_map.config import (
    is_repomap_enabled,
    load_repomap_config,
    load_repomap_status,
    write_repomap_config,
    write_repomap_status,
)
from aictx.repo_map.paths import (
    repo_map_config_path,
    repo_map_index_path,
    repo_map_manifest_path,
    repo_map_status_path,
)
from aictx.state import REPO_MAP_CONFIG_PATH, REPO_MAP_INDEX_PATH, REPO_MAP_MANIFEST_PATH, REPO_MAP_STATUS_PATH


def test_repomap_paths_match_repo_local_contract(tmp_path: Path):
    assert repo_map_config_path(tmp_path) == tmp_path / REPO_MAP_CONFIG_PATH
    assert repo_map_manifest_path(tmp_path) == tmp_path / REPO_MAP_MANIFEST_PATH
    assert repo_map_index_path(tmp_path) == tmp_path / REPO_MAP_INDEX_PATH
    assert repo_map_status_path(tmp_path) == tmp_path / REPO_MAP_STATUS_PATH


def test_default_config_is_disabled(tmp_path: Path):
    payload = load_repomap_config(tmp_path)
    assert payload == {
        "version": 1,
        "enabled": False,
        "provider": "tree_sitter",
        "quick_refresh_budget_ms": 300,
        "quick_refresh_max_files": 20,
        "max_parse_file_bytes": 512000,
    }
    assert is_repomap_enabled(tmp_path) is False


def test_write_enabled_config_persists_correctly(tmp_path: Path):
    write_repomap_config(
        tmp_path,
        {
            "enabled": True,
            "quick_refresh_budget_ms": 1200,
            "quick_refresh_max_files": 10,
            "max_parse_file_bytes": 1024,
        },
    )
    payload = load_repomap_config(tmp_path)
    assert payload["enabled"] is True
    assert payload["provider"] == "tree_sitter"
    assert payload["quick_refresh_budget_ms"] == 1200
    assert payload["quick_refresh_max_files"] == 10
    assert payload["max_parse_file_bytes"] == 1024
    assert is_repomap_enabled(tmp_path) is True


def test_status_write_and_read_preserve_fields(tmp_path: Path):
    write_repomap_status(
        tmp_path,
        {
            "enabled": True,
            "available": True,
            "last_refresh_status": "ok",
            "warnings": ["sample-warning"],
        },
    )
    payload = load_repomap_status(tmp_path)
    assert payload == {
        "version": 1,
        "enabled": True,
        "available": True,
        "provider": "tree_sitter",
        "last_refresh_mode": "",
        "last_refresh_status": "ok",
        "last_refresh_ms": 0,
        "files_reparsed": 0,
        "files_pending": 0,
        "warnings": ["sample-warning"],
    }


def test_task2_does_not_import_tree_sitter_dependency(tmp_path: Path):
    _ = load_repomap_config(tmp_path)
    _ = load_repomap_status(tmp_path)
    assert "tree_sitter_language_pack" not in sys.modules

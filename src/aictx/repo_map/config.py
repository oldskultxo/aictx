from __future__ import annotations

from pathlib import Path
from typing import Any

from ..state import read_json, write_json
from .models import normalize_repomap_config, normalize_repomap_status
from .paths import repo_map_config_path, repo_map_index_path, repo_map_manifest_path, repo_map_status_path


def load_repomap_config(repo_root: Path) -> dict[str, Any]:
    raw = read_json(repo_map_config_path(repo_root), {})
    if not isinstance(raw, dict):
        raw = {}
    return normalize_repomap_config(raw)


def write_repomap_config(repo_root: Path, payload: dict[str, Any]) -> None:
    write_json(repo_map_config_path(repo_root), normalize_repomap_config(payload))


def load_repomap_status(repo_root: Path) -> dict[str, Any]:
    raw = read_json(repo_map_status_path(repo_root), {})
    if not isinstance(raw, dict):
        raw = {}
    return normalize_repomap_status(raw)


def write_repomap_status(repo_root: Path, payload: dict[str, Any]) -> None:
    write_json(repo_map_status_path(repo_root), normalize_repomap_status(payload))


def is_repomap_enabled(repo_root: Path) -> bool:
    return bool(load_repomap_config(repo_root).get("enabled", False))


def load_repomap_index(repo_root: Path) -> dict[str, Any]:
    raw = read_json(repo_map_index_path(repo_root), {})
    return raw if isinstance(raw, dict) else {}


def write_repomap_index(repo_root: Path, payload: dict[str, Any]) -> None:
    write_json(repo_map_index_path(repo_root), payload)


def load_repomap_manifest(repo_root: Path) -> dict[str, Any]:
    raw = read_json(repo_map_manifest_path(repo_root), {})
    return raw if isinstance(raw, dict) else {}


def write_repomap_manifest(repo_root: Path, payload: dict[str, Any]) -> None:
    write_json(repo_map_manifest_path(repo_root), payload)


def resolve_repo_repomap_config(global_config: dict[str, Any] | None) -> dict[str, Any]:
    payload = dict(global_config or {})
    repomap = payload.get("repomap", {}) if isinstance(payload.get("repomap"), dict) else {}
    return normalize_repomap_config(
        {
            "enabled": bool(repomap.get("requested", False)),
            "provider": str(repomap.get("provider") or "tree_sitter"),
        }
    )

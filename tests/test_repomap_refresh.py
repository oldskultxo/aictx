from __future__ import annotations

import json
from pathlib import Path

import aictx.repo_map.refresh as refresh_module
from aictx.repo_map.config import load_repomap_manifest, load_repomap_status, write_repomap_config
from aictx.repo_map.paths import repo_map_index_path


def test_full_refresh_writes_index_manifest_status(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "one.py").write_text("print('x')\n", encoding="utf-8")
    write_repomap_config(repo, {"enabled": True})

    monkeypatch.setattr(refresh_module, "check_tree_sitter_available", lambda: {"available": True, "provider": "tree_sitter", "version": "x", "languages_count": 1, "error": ""})
    monkeypatch.setattr(
        refresh_module,
        "extract_file_structure",
        lambda path, repo_root, max_parse_file_bytes: {
            "path": Path(path).relative_to(repo_root).as_posix(),
            "language": "python",
            "symbols": [{"name": "main", "kind": "function", "line": 1, "end_line": 1, "language": "python"}],
            "imports": [],
            "metadata_only": False,
            "provider": "tree_sitter",
            "reason": "",
            "size_bytes": 12,
        },
    )

    payload = refresh_module.refresh_repo_map(repo)

    assert payload["status"] == "ok"
    assert payload["mode"] == "full"
    assert payload["files_discovered"] == 2
    assert payload["files_indexed"] == 2
    assert payload["symbols_indexed"] == 2
    assert repo_map_index_path(repo).exists()
    assert load_repomap_manifest(repo)["files_indexed"] == 2
    assert load_repomap_status(repo)["last_refresh_status"] == "ok"


def test_metadata_only_files_are_included(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "large.py").write_text("print('x')\n", encoding="utf-8")
    write_repomap_config(repo, {"enabled": False})

    monkeypatch.setattr(refresh_module, "check_tree_sitter_available", lambda: {"available": True, "provider": "tree_sitter", "version": "x", "languages_count": 1, "error": ""})
    monkeypatch.setattr(
        refresh_module,
        "extract_file_structure",
        lambda path, repo_root, max_parse_file_bytes: {
            "path": Path(path).relative_to(repo_root).as_posix(),
            "language": "python",
            "symbols": [],
            "imports": [],
            "metadata_only": True,
            "provider": "tree_sitter",
            "reason": "file_too_large",
            "size_bytes": 999,
        },
    )

    refresh_module.refresh_repo_map(repo)
    payload = json.loads(repo_map_index_path(repo).read_text(encoding="utf-8"))
    assert payload["files"][0]["metadata_only"] is True
    assert payload["files"][0]["reason"] == "file_too_large"


def test_provider_unavailable_produces_status_unavailable(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()

    monkeypatch.setattr(refresh_module, "check_tree_sitter_available", lambda: {"available": False, "provider": "tree_sitter", "version": "", "languages_count": 0, "error": "missing_dependency"})

    payload = refresh_module.refresh_repo_map(repo)

    assert payload == {"status": "unavailable", "reason": "missing_dependency"}
    status = load_repomap_status(repo)
    assert status["available"] is False
    assert status["last_refresh_status"] == "unavailable"

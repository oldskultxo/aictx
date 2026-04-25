from __future__ import annotations

import argparse
from pathlib import Path

import aictx.cli as cli
from aictx.repo_map.config import load_repomap_config, load_repomap_status
from aictx.repo_map.paths import repo_map_index_path, repo_map_manifest_path, repo_map_status_path
from aictx.scaffold import init_repo_scaffold
from aictx.state import Workspace, write_json


def _init_args(repo: Path) -> argparse.Namespace:
    return argparse.Namespace(repo=str(repo), yes=True, no_gitignore=True, no_register=True)


def _patch_init_environment(monkeypatch, global_config: dict):
    monkeypatch.setattr(cli, "ensure_global_home", lambda: None)
    monkeypatch.setattr(cli, "install_global_agent_runtime", lambda _write_json: [])
    monkeypatch.setattr(cli, "copy_local_agent_runtime", lambda repo: repo / ".aictx" / "local_agent_runtime.md")
    monkeypatch.setattr(cli, "prepare_repo_runtime", lambda repo: [])
    monkeypatch.setattr(cli, "install_repo_runner_integrations", lambda repo: [])
    monkeypatch.setattr(cli, "upsert_marked_block", lambda *args, **kwargs: None)
    monkeypatch.setattr(cli, "remove_marked_block", lambda *args, **kwargs: None)
    monkeypatch.setattr(cli, "persist_repo_communication_mode", lambda repo, mode: None)
    monkeypatch.setattr(cli, "load_active_workspace", lambda: Workspace(workspace_id="default", roots=[], repos=[]))
    monkeypatch.setattr(cli, "save_workspace", lambda ws: None)
    monkeypatch.setattr(cli, "resolve_workspace_root", lambda repo, roots: None)

    def fake_read_json(path: Path, default):
        if path == cli.CONFIG_PATH:
            return global_config
        if path == cli.PROJECTS_REGISTRY_PATH:
            return {"version": 1, "projects": []}
        return default

    monkeypatch.setattr(cli, "read_json", fake_read_json)


def test_init_without_repomap_behaves_as_before(tmp_path: Path, monkeypatch, capsys):
    repo = tmp_path / "repo"
    _patch_init_environment(monkeypatch, {"version": 1})
    refresh_called = {"value": False}
    monkeypatch.setattr(cli, "refresh_repo_map", lambda *args, **kwargs: refresh_called.__setitem__("value", True))

    assert cli.cmd_init(_init_args(repo)) == 0

    out = capsys.readouterr().out
    assert "Init complete. Use your coding agent normally in this repo." in out
    assert not (repo / ".aictx" / "repo_map" / "config.json").exists()
    assert refresh_called["value"] is False


def test_init_with_global_repomap_enabled_writes_repo_config(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    _patch_init_environment(monkeypatch, {"version": 1, "repomap": {"requested": True, "provider": "tree_sitter", "available": True}})
    monkeypatch.setattr(cli, "check_tree_sitter_available", lambda: {"available": False, "provider": "tree_sitter", "version": "", "languages_count": 0, "error": "missing_dependency"})
    monkeypatch.setattr(cli, "refresh_repo_map", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("provider unavailable should skip refresh")))

    assert cli.cmd_init(_init_args(repo)) == 0

    assert load_repomap_config(repo)["enabled"] is True


def test_init_with_provider_unavailable_succeeds_and_records_status(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    _patch_init_environment(monkeypatch, {"version": 1, "repomap": {"requested": True, "provider": "tree_sitter", "available": True}})
    monkeypatch.setattr(cli, "check_tree_sitter_available", lambda: {"available": False, "provider": "tree_sitter", "version": "", "languages_count": 0, "error": "missing_dependency"})
    monkeypatch.setattr(cli, "refresh_repo_map", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("refresh should not run when provider unavailable")))

    assert cli.cmd_init(_init_args(repo)) == 0

    status = load_repomap_status(repo)
    assert status["last_refresh_status"] == "unavailable"
    assert status["warnings"] == ["missing_dependency"]


def test_init_with_fake_provider_available_writes_index_manifest_status(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    _patch_init_environment(monkeypatch, {"version": 1, "repomap": {"requested": True, "provider": "tree_sitter", "available": True}})
    monkeypatch.setattr(cli, "check_tree_sitter_available", lambda: {"available": True, "provider": "tree_sitter", "version": "x", "languages_count": 1, "error": ""})

    def fake_refresh(repo_root: Path, mode: str = "full", **kwargs):
        assert mode == "full"
        write_json(repo_map_index_path(repo_root), {"version": 1, "files": [{"path": "src/aictx/cli.py"}]})
        write_json(repo_map_manifest_path(repo_root), {"version": 1, "files_indexed": 1, "symbols_indexed": 1})
        write_json(repo_map_status_path(repo_root), {"version": 1, "enabled": True, "available": True, "provider": "tree_sitter", "last_refresh_status": "ok", "warnings": []})
        return {"status": "ok", "mode": "full"}

    monkeypatch.setattr(cli, "refresh_repo_map", fake_refresh)

    assert cli.cmd_init(_init_args(repo)) == 0

    assert repo_map_index_path(repo).exists()
    assert repo_map_manifest_path(repo).exists()
    assert repo_map_status_path(repo).exists()

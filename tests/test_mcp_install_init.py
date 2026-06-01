from __future__ import annotations

import json
from pathlib import Path

from aictx.integrations.mcp_config import install_global_mcp_config, install_repo_mcp_config, mcp_server_command, mcp_status, remove_repo_mcp_config
from aictx.scaffold import init_repo_scaffold
import aictx.state as state_module


def test_repo_mcp_config_default_and_idempotent(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    first = install_repo_mcp_config(repo, profile="full")
    second = install_repo_mcp_config(repo, profile="full")
    assert first["changed"] is True
    assert second["changed"] is False
    payload = json.loads((repo / ".mcp.json").read_text(encoding="utf-8"))
    vscode = json.loads((repo / ".vscode" / "mcp.json").read_text(encoding="utf-8"))
    assert payload["_aictx"]["block"] == "<AICTX>"
    assert payload["mcpServers"]["aictx"]["_aictx_block"] == "<AICTX>"
    assert payload["mcpServers"]["aictx"]["args"] == ["mcp-server", "--repo", ".", "--profile", "full"]
    assert payload["mcpServers"]["aictx"]["type"] == "stdio"
    assert mcp_server_command("full") == ["aictx", "mcp-server", "--repo", ".", "--profile", "full"]
    assert "servers" not in payload
    assert vscode["_aictx"]["block"] == "<AICTX>"
    assert vscode["servers"]["aictx"]["_aictx_block"] == "<AICTX>"
    assert vscode["servers"]["aictx"]["args"] == ["mcp-server", "--repo", ".", "--profile", "full"]
    assert vscode["servers"]["aictx"]["type"] == "stdio"
    assert "mcpServers" not in vscode


def test_repo_mcp_config_uses_local_source_checkout_runtime(tmp_path: Path):
    repo = tmp_path / "aictx"
    (repo / "src" / "aictx").mkdir(parents=True)
    (repo / "src" / "aictx" / "__init__.py").write_text("", encoding="utf-8")
    (repo / "pyproject.toml").write_text('[project]\nname = "aictx"\n', encoding="utf-8")
    venv_bin = repo / ".venv" / ("Scripts" if __import__("os").name == "nt" else "bin")
    venv_bin.mkdir(parents=True)
    python = venv_bin / ("python.exe" if __import__("os").name == "nt" else "python")
    python.write_text("", encoding="utf-8")

    install_repo_mcp_config(repo, profile="readonly")

    payload = json.loads((repo / ".mcp.json").read_text(encoding="utf-8"))
    entry = payload["mcpServers"]["aictx"]
    assert entry["command"] == str(python.relative_to(repo))
    assert entry["args"] == ["-m", "aictx", "mcp-server", "--repo", ".", "--profile", "readonly"]
    assert entry["cwd"] == "."
    assert entry["env"] == {"PYTHONPATH": "src"}
    assert entry["type"] == "stdio"


def test_global_mcp_config_uses_managed_status(tmp_path: Path, monkeypatch):
    engine = tmp_path / ".aictx"
    monkeypatch.setattr(state_module, "ENGINE_HOME", engine)
    monkeypatch.setattr(state_module, "CONFIG_PATH", engine / "config.json")
    payload = install_global_mcp_config(profile="readonly")
    assert payload["enabled"] is True
    assert (engine / "mcp" / "status.json").exists()
    assert mcp_status(tmp_path)["global"]["profile"] == "readonly"


def test_mcp_status_only_enables_repo_when_aictx_server_is_present(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    (repo / ".vscode").mkdir()
    (repo / ".vscode" / "mcp.json").write_text(json.dumps({"servers": {"other": {"command": "other"}}}), encoding="utf-8")

    missing = mcp_status(repo)["repo"]

    assert missing["enabled"] is False
    assert missing["files"] == []

    (repo / ".mcp.json").write_text(json.dumps({"mcpServers": {"aictx": {"command": "custom-aictx"}}}), encoding="utf-8")
    present = mcp_status(repo)["repo"]

    assert present["enabled"] is True
    assert present["files"] == [str(repo / ".mcp.json")]


def test_repo_mcp_cleanup_handles_both_container_shapes_and_preserves_user_servers(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    (repo / ".mcp.json").write_text(json.dumps({"mcpServers": {"aictx": {"command": "aictx", "_aictx_managed": True}, "other": {"command": "other"}}}), encoding="utf-8")
    (repo / ".vscode").mkdir()
    (repo / ".vscode" / "mcp.json").write_text(json.dumps({"servers": {"aictx": {"command": "aictx", "_aictx_managed": True}, "copilot-user": {"command": "user"}}}), encoding="utf-8")

    result = remove_repo_mcp_config(repo)

    assert str(repo / ".mcp.json") in result["updated"]
    assert str(repo / ".vscode" / "mcp.json") in result["updated"]
    root_payload = json.loads((repo / ".mcp.json").read_text(encoding="utf-8"))
    vscode_payload = json.loads((repo / ".vscode" / "mcp.json").read_text(encoding="utf-8"))
    assert root_payload == {"mcpServers": {"other": {"command": "other"}}}
    assert vscode_payload == {"servers": {"copilot-user": {"command": "user"}}}

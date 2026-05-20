from __future__ import annotations

import json
from pathlib import Path

from aictx.integrations.mcp_config import install_global_mcp_config, install_repo_mcp_config, mcp_status
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
    assert payload["mcpServers"]["aictx"]["args"] == ["mcp-server", "--repo", ".", "--profile", "full"]


def test_global_mcp_config_uses_managed_status(tmp_path: Path, monkeypatch):
    engine = tmp_path / ".aictx"
    monkeypatch.setattr(state_module, "ENGINE_HOME", engine)
    monkeypatch.setattr(state_module, "CONFIG_PATH", engine / "config.json")
    payload = install_global_mcp_config(profile="readonly")
    assert payload["enabled"] is True
    assert (engine / "mcp" / "status.json").exists()
    assert mcp_status(tmp_path)["global"]["profile"] == "readonly"

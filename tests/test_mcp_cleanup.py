from __future__ import annotations

import json
from pathlib import Path

from aictx.cleanup import clean_repo
from aictx.integrations.mcp_config import install_repo_mcp_config
from aictx.scaffold import init_repo_scaffold


def test_clean_removes_managed_mcp_and_preserves_user_server(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    install_repo_mcp_config(repo)
    user_config = {"mcpServers": {"other": {"command": "other"}}}
    (repo / ".vscode" / "mcp.json").write_text(json.dumps(user_config | {"mcpServers": {**user_config["mcpServers"], "aictx": {"command": "aictx", "_aictx_managed": True}}}), encoding="utf-8")
    result = clean_repo(repo)
    assert str(repo / ".mcp.json") in result["removed"]
    remaining = json.loads((repo / ".vscode" / "mcp.json").read_text(encoding="utf-8"))
    assert "other" in remaining["mcpServers"]
    assert "aictx" not in remaining["mcpServers"]

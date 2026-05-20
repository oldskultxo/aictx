from __future__ import annotations

import json
from pathlib import Path

from aictx.cleanup import clean_repo, remove_codex_config_aictx_entries
from aictx.integrations.mcp_config import install_repo_mcp_config
from aictx.scaffold import init_repo_scaffold


def test_clean_removes_managed_mcp_and_preserves_user_server(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    install_repo_mcp_config(repo)
    user_config = {"servers": {"other": {"command": "other"}}}
    (repo / ".vscode" / "mcp.json").write_text(json.dumps(user_config | {"servers": {**user_config["servers"], "aictx": {"command": "aictx", "_aictx_managed": True}}}), encoding="utf-8")
    result = clean_repo(repo)
    assert str(repo / ".mcp.json") in result["removed"]
    remaining = json.loads((repo / ".vscode" / "mcp.json").read_text(encoding="utf-8"))
    assert "other" in remaining["servers"]
    assert "aictx" not in remaining["servers"]


def test_codex_config_cleanup_removes_aictx_mcp_block_and_preserves_user_config(tmp_path: Path):
    config = tmp_path / "config.toml"
    config.write_text(
        "\n".join(
            [
                'model = "gpt-5.4"',
                "",
                "# <AICTX:START mcp>",
                "# AICTX managed MCP server for repo-local continuity; safe to remove as one block.",
                "[mcp_servers.aictx]",
                'command = "aictx"',
                'args = ["mcp-server", "--repo", ".", "--profile", "full"]',
                "# <AICTX:END mcp>",
                "",
                "[mcp_servers.user]",
                'command = "user"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    assert remove_codex_config_aictx_entries(config) is True

    text = config.read_text(encoding="utf-8")
    assert "<AICTX" not in text
    assert "[mcp_servers.aictx]" not in text
    assert 'model = "gpt-5.4"' in text
    assert "[mcp_servers.user]" in text


def test_codex_config_cleanup_removes_legacy_unmarked_aictx_mcp_section(tmp_path: Path):
    config = tmp_path / "config.toml"
    config.write_text(
        "\n".join(
            [
                'model = "gpt-5.4"',
                "",
                "[mcp_servers.aictx]",
                'command = "aictx"',
                'args = ["mcp-server", "--repo", ".", "--profile", "full"]',
                "",
                "[mcp_servers.user]",
                'command = "user"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    assert remove_codex_config_aictx_entries(config) is True

    text = config.read_text(encoding="utf-8")
    assert "[mcp_servers.aictx]" not in text
    assert "[mcp_servers.user]" in text

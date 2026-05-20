from __future__ import annotations

from pathlib import Path

from aictx.mcp.server import handle_request
from aictx.scaffold import init_repo_scaffold


def test_mcp_server_initialize_and_lists(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    init = handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}, repo=str(repo), profile="full")
    assert init["result"]["serverInfo"]["name"] == "aictx"

    tools = handle_request({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}, repo=str(repo), profile="readonly")
    names = {tool["name"] for tool in tools["result"]["tools"]}
    assert "aictx_resume" in names
    assert "aictx_finalize" not in names

    resources = handle_request({"jsonrpc": "2.0", "id": 3, "method": "resources/list", "params": {}}, repo=str(repo), profile="full")
    assert "aictx://repo/current/doctor" in {item["uri"] for item in resources["result"]["resources"]}

    prompts = handle_request({"jsonrpc": "2.0", "id": 4, "method": "prompts/list", "params": {}}, repo=str(repo), profile="full")
    assert "aictx_continue_task" in {item["name"] for item in prompts["result"]["prompts"]}


def test_mcp_tool_permission_and_unknown_tool(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    denied = handle_request({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "aictx_finalize", "arguments": {"status": "success", "summary": "done"}}}, repo=str(repo), profile="readonly")
    assert denied["result"]["structuredContent"]["error"]["code"] == "permission_denied"
    unknown = handle_request({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "missing", "arguments": {}}}, repo=str(repo), profile="full")
    assert unknown["result"]["structuredContent"]["error"]["code"] == "unknown_tool"

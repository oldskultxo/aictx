from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import aictx
from aictx.mcp.server import DEFAULT_PROTOCOL_VERSION, handle_request
from aictx.scaffold import init_repo_scaffold


def test_mcp_server_initialize_negotiates_protocol_and_reports_version(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)

    latest = handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}}, repo=str(repo), profile="full")
    legacy = handle_request({"jsonrpc": "2.0", "id": 2, "method": "initialize", "params": {"protocolVersion": "2024-11-05"}}, repo=str(repo), profile="full")
    unknown = handle_request({"jsonrpc": "2.0", "id": 3, "method": "initialize", "params": {"protocolVersion": "unknown"}}, repo=str(repo), profile="full")
    malformed = handle_request({"jsonrpc": "2.0", "id": 4, "method": "initialize", "params": "bad"}, repo=str(repo), profile="full")

    assert latest["result"]["protocolVersion"] == "2025-06-18"
    assert legacy["result"]["protocolVersion"] == "2024-11-05"
    assert unknown["result"]["protocolVersion"] == DEFAULT_PROTOCOL_VERSION
    assert malformed["result"]["protocolVersion"] == DEFAULT_PROTOCOL_VERSION
    assert latest["result"]["serverInfo"] == {"name": "aictx", "version": aictx.__version__}


def test_mcp_server_lists_resources_prompts_and_readonly_tools(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)

    tools = handle_request({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}, repo=str(repo), profile="readonly")
    names = {tool["name"] for tool in tools["result"]["tools"]}
    assert "aictx_resume" in names
    assert "aictx_finalize" not in names
    resume = next(tool for tool in tools["result"]["tools"] if tool["name"] == "aictx_resume")
    assert "task" in resume["inputSchema"]["properties"]

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


def test_mcp_stdio_subprocess_json_rpc_is_stdout_clean(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    messages = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "0"}}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
    ]
    proc = subprocess.Popen(
        [sys.executable, "-m", "aictx.cli", "mcp-server", "--repo", str(repo), "--profile", "readonly"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=os.environ.copy(),
    )
    stdout, stderr = proc.communicate("".join(json.dumps(message) + "\n" for message in messages), timeout=10)

    assert proc.returncode == 0
    assert stderr.strip() == "" or "jsonrpc" not in stderr.lower()
    lines = [line for line in stdout.splitlines() if line.strip()]
    assert len(lines) == 2
    responses = [json.loads(line) for line in lines]
    assert responses[0]["result"]["serverInfo"]["name"] == "aictx"
    names = {tool["name"] for tool in responses[1]["result"]["tools"]}
    assert "aictx_resume" in names
    assert "aictx_finalize" not in names

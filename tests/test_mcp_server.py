from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import aictx
from aictx.mcp.server import DEFAULT_PROTOCOL_VERSION, handle_request
from aictx.scaffold import init_repo_scaffold
from aictx.state import REPO_CONTINUITY_SESSION_PATH, read_json


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
    assert "aictx_lifecycle_status" in names
    assert "aictx_finalize" not in names
    resume = next(tool for tool in tools["result"]["tools"] if tool["name"] == "aictx_resume")
    assert "task" in resume["inputSchema"]["properties"]

    resources = handle_request({"jsonrpc": "2.0", "id": 3, "method": "resources/list", "params": {}}, repo=str(repo), profile="full")
    assert "aictx://repo/current/doctor" in {item["uri"] for item in resources["result"]["resources"]}
    assert "aictx://repo/current/continuity-quality" in {item["uri"] for item in resources["result"]["resources"]}
    assert "aictx://repo/current/lifecycle-status" in {item["uri"] for item in resources["result"]["resources"]}

    prompts = handle_request({"jsonrpc": "2.0", "id": 4, "method": "prompts/list", "params": {}}, repo=str(repo), profile="full")
    assert "aictx_continue_task" in {item["name"] for item in prompts["result"]["prompts"]}


def test_mcp_tool_permission_and_unknown_tool(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    denied = handle_request({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "aictx_finalize", "arguments": {"status": "success", "summary": "done"}}}, repo=str(repo), profile="readonly")
    assert denied["result"]["structuredContent"]["error"]["code"] == "permission_denied"
    unknown = handle_request({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "missing", "arguments": {}}}, repo=str(repo), profile="full")
    assert unknown["result"]["structuredContent"]["error"]["code"] == "unknown_tool"


def test_mcp_resume_infers_claude_code_identity(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(repo))

    response = handle_request(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "aictx_resume", "arguments": {"task": "inspect claude mcp"}}},
        repo=str(repo),
        profile="full",
    )

    payload = response["result"]["structuredContent"]["continuity_brief"]
    assert payload["agent_id"] == "claude"
    assert payload["adapter_id"] == "claude"
    assert payload["startup_banner_render_payload"]["header"]["agent_label"] == f"claude@{repo.name}"


def test_mcp_resume_infers_copilot_identity(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    monkeypatch.setenv("GITHUB_COPILOT_AGENT", "1")

    response = handle_request(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "aictx_resume", "arguments": {"task": "inspect copilot mcp"}}},
        repo=str(repo),
        profile="full",
    )

    payload = response["result"]["structuredContent"]["continuity_brief"]
    assert payload["agent_id"] == "copilot"
    assert payload["adapter_id"] == "copilot"
    assert payload["startup_banner_render_payload"]["header"]["agent_label"] == f"copilot@{repo.name}"


def test_mcp_resume_and_finalize_preserve_codex_identity(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    monkeypatch.setenv("CODEX_THREAD_ID", "thread-123")

    resume_call = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": "aictx_resume", "arguments": {"task": "inspect startup banner"}},
    }
    first = handle_request(resume_call, repo=str(repo), profile="full")
    first_payload = first["result"]["structuredContent"]["continuity_brief"]
    assert first_payload["startup_banner_render_payload"]["header"]["agent_label"] == f"codex@{repo.name}"
    assert first_payload["startup_banner_policy"]["already_shown"] is False

    finalize_call = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {"name": "aictx_finalize", "arguments": {"status": "success", "summary": "startup banner shown once"}},
    }
    finalized = handle_request(finalize_call, repo=str(repo), profile="full")
    assert finalized["result"]["structuredContent"]["finalize"]["telemetry_entry"]["agent_id"] == "codex"
    assert read_json(repo / REPO_CONTINUITY_SESSION_PATH, {})["agent_label"] == f"codex@{repo.name}"

    second = handle_request(resume_call, repo=str(repo), profile="full")
    second_payload = second["result"]["structuredContent"]["continuity_brief"]
    assert second_payload["startup_banner_text"] == ""
    assert second_payload["startup_banner_policy"]["already_shown"] is True


def test_mcp_stdio_subprocess_json_rpc_is_stdout_clean(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    messages = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "0"}}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
    ]
    project_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(project_root / "src") + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    proc = subprocess.Popen(
        [sys.executable, "-m", "aictx.cli", "mcp-server", "--repo", str(repo), "--profile", "readonly"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=str(project_root),
        env=env,
    )
    stdout, stderr = proc.communicate("".join(json.dumps(message) + "\n" for message in messages), timeout=10)

    assert proc.returncode == 0, stderr
    assert stderr.strip() == "" or "jsonrpc" not in stderr.lower()
    lines = [line for line in stdout.splitlines() if line.strip()]
    assert len(lines) == 2
    responses = [json.loads(line) for line in lines]
    assert responses[0]["result"]["serverInfo"]["name"] == "aictx"
    names = {tool["name"] for tool in responses[1]["result"]["tools"]}
    assert "aictx_resume" in names
    assert "aictx_finalize" not in names


def test_mcp_lifecycle_status_tool_and_resource(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)

    tool = handle_request({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "aictx_lifecycle_status", "arguments": {"task": "fix parser"}}}, repo=str(repo), profile="readonly")
    assert tool["result"]["structuredContent"]["ok"] is True
    assert tool["result"]["structuredContent"]["lifecycle_status"]["status"] == "ok"

    resource = handle_request({"jsonrpc": "2.0", "id": 2, "method": "resources/read", "params": {"uri": "aictx://repo/current/lifecycle-status"}}, repo=str(repo), profile="readonly")
    assert '"status": "ok"' in resource["result"]["contents"][0]["text"]


def test_mcp_stdio_subprocess_preserves_content_length_framing(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    message = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "0"}}}
    raw_message = json.dumps(message).encode("utf-8")
    framed_message = b"Content-Length: " + str(len(raw_message)).encode("ascii") + b"\r\n\r\n" + raw_message
    project_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(project_root / "src") + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    proc = subprocess.Popen(
        [sys.executable, "-m", "aictx.cli", "mcp-server", "--repo", str(repo), "--profile", "readonly"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(project_root),
        env=env,
    )
    stdout, stderr = proc.communicate(framed_message, timeout=10)

    assert proc.returncode == 0, stderr.decode("utf-8", errors="replace")
    assert stdout.startswith(b"Content-Length: ")
    header, body = stdout.split(b"\r\n\r\n", 1)
    length = int(header.split(b":", 1)[1].strip())
    assert length == len(body)
    response = json.loads(body.decode("utf-8"))
    assert response["result"]["serverInfo"]["name"] == "aictx"

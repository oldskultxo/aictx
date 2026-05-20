from __future__ import annotations

from pathlib import Path

from aictx.mcp.tools import call_tool
from aictx.scaffold import init_repo_scaffold


def test_mcp_resume_finalize_and_work_state(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    resumed = call_tool("aictx_resume", {"repo": str(repo), "task": "add tests"})
    assert resumed["ok"] is True
    assert resumed["mode"] == "standard"

    started = call_tool("aictx_task_start", {"repo": str(repo), "goal": "MCP task", "files": ["src/aictx/mcp/tools.py"]})
    task_id = started["task"]["task_id"]
    updated = call_tool("aictx_task_update", {"repo": str(repo), "task_id": task_id, "next_action": "verify"})
    assert updated["changed"] is True
    closed = call_tool("aictx_task_close", {"repo": str(repo), "task_id": task_id, "status": "resolved", "summary": "done"})
    assert closed["ok"] is True

    finalized = call_tool("aictx_finalize", {"repo": str(repo), "status": "success", "summary": "MCP finalized", "files_edited": ["src/aictx/mcp/tools.py"]})
    assert finalized["ok"] is True
    assert finalized["changed"] is True


def test_mcp_map_portability_and_view_tools(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    assert call_tool("aictx_map_query", {"repo": str(repo), "query": "missing", "limit": 2})["ok"] is True
    assert call_tool("aictx_portability_status", {"repo": str(repo)})["ok"] is True
    view = call_tool("aictx_continuity_view_generate", {"repo": str(repo)})
    assert view["ok"] is True
    assert (repo / ".aictx" / "reports" / "continuity-view.md").exists()


def test_mcp_security_invalid_repo_and_payload_limit(tmp_path: Path):
    bad = call_tool("aictx_resume", {"repo": str(tmp_path / "missing"), "task": "x"})
    assert bad["error"]["code"] == "invalid_request"
    too_large = call_tool("aictx_record_decision", {"repo": str(tmp_path), "title": "x", "decision": "x" * 13000})
    assert too_large["error"]["code"] == "invalid_request"

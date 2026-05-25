from __future__ import annotations

import json
from pathlib import Path

from aictx import cli
from aictx.continuity import DECISIONS_PATH, HANDOFF_PATH
from aictx.mcp.permissions import allowed_tools
from aictx.mcp.server import handle_request
from aictx.mcp.tools import call_tool, tool_specs
from aictx.repo_map.config import write_repomap_config, write_repomap_index
from aictx.scaffold import init_repo_scaffold


def _parser():
    return cli.build_parser()


def _seed_task_repo(repo: Path) -> None:
    (repo / "src/taskflow").mkdir(parents=True, exist_ok=True)
    (repo / "src/taskflow/parser.py").write_text("def parse_blocked():\n    pass\n", encoding="utf-8")
    (repo / "tests").mkdir(exist_ok=True)
    (repo / "tests/test_parser.py").write_text("def test_blocked_edge_cases():\n    pass\n", encoding="utf-8")
    (repo / ".github/workflows").mkdir(parents=True, exist_ok=True)
    (repo / ".github/workflows/publish.yml").write_text("name: publish\n", encoding="utf-8")
    (repo / "README.md").write_text("# Parser docs\n", encoding="utf-8")
    write_repomap_config(repo, {"enabled": True})
    write_repomap_index(
        repo,
        {
            "version": 1,
            "files": [
                {"path": "README.md", "language": "markdown", "symbols": [{"name": "Parser docs", "kind": "heading", "line": 1, "language": "markdown"}]},
                {"path": "src/taskflow/parser.py", "language": "python", "symbols": [{"name": "parse_blocked", "kind": "function", "line": 1, "language": "python"}]},
                {"path": "tests/test_parser.py", "language": "python", "symbols": [{"name": "test_blocked_edge_cases", "kind": "function", "line": 1, "language": "python"}]},
            ],
        },
    )


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_prepare_cli_json_returns_task_context_pack_and_prefers_source(tmp_path: Path, capsys) -> None:
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    _seed_task_repo(repo)
    _write_jsonl(
        repo / DECISIONS_PATH,
        [
            {"decision": "Publish releases through the GitHub workflow.", "timestamp": "2026-05-24T00:00:00Z", "related_paths": [".github/workflows/publish.yml"], "subsystem": "release"},
            {"decision": "Parser changes require focused parser tests.", "timestamp": "2026-05-24T00:00:00Z", "related_paths": ["src/taskflow/parser.py"], "subsystem": "parser"},
        ],
    )

    args = _parser().parse_args(["prepare", "fix blocked parser bug", "--repo", str(repo), "--json"])
    assert args.func(args) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["mode"] == "task_context_pack"
    assert payload["goal"]["normalized"] == "fix blocked parser bug"
    assert payload["task_type"] == "bug_fixing"
    paths = [item["path"] for item in payload["relevant_files"]]
    assert "src/taskflow/parser.py" in paths
    assert ".github/workflows/publish.yml" not in paths
    assert paths.index("src/taskflow/parser.py") < paths.index("README.md") if "README.md" in paths else True
    assert payload["repo_map_entrypoints"]
    assert payload["decisions"][0]["decision"] == "Parser changes require focused parser tests."
    assert payload["execution_contract"]["read_only_pack"] is True
    assert not (repo / ".aictx" / "continuity" / "task_context_pack.json").exists()


def test_prepare_cli_markdown_and_missing_repomap_fallback(tmp_path: Path, capsys) -> None:
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)

    args = _parser().parse_args(["prepare", "add feature", "--repo", str(repo)])
    assert args.func(args) == 0

    output = capsys.readouterr().out
    assert output.startswith("Task Context Pack\n")
    assert "Goal:" in output
    assert "RepoMap did not return task-specific entrypoints" in output


def test_prepare_flags_stale_or_missing_context(tmp_path: Path, capsys) -> None:
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    _seed_task_repo(repo)
    (repo / HANDOFF_PATH).write_text(json.dumps({"summary": "old deleted path", "updated_at": "2026-05-24T00:00:00Z", "recommended_starting_points": ["src/deleted.py"]}), encoding="utf-8")

    args = _parser().parse_args(["prepare", "fix parser", "--repo", str(repo), "--json"])
    assert args.func(args) == 0
    payload = json.loads(capsys.readouterr().out)

    assert any(item["code"] == "missing_linked_file" for item in payload["staleness_warnings"])


def test_prepare_mcp_tool_is_readonly_and_requires_goal(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    _seed_task_repo(repo)

    readonly_names = allowed_tools("readonly")
    assert "aictx_prepare_task_context" in readonly_names
    specs = {tool["name"]: tool for tool in tool_specs()}
    assert specs["aictx_prepare_task_context"]["inputSchema"]["required"] == ["goal"]

    bad = call_tool("aictx_prepare_task_context", {"repo": str(repo)})
    assert bad["ok"] is False
    assert bad["error"]["code"] == "invalid_request"

    response = handle_request(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "aictx_prepare_task_context", "arguments": {"goal": "fix blocked parser bug"}}},
        repo=str(repo),
        profile="readonly",
    )
    structured = response["result"]["structuredContent"]
    assert structured["ok"] is True
    assert structured["task_context_pack"]["goal"]["normalized"] == "fix blocked parser bug"

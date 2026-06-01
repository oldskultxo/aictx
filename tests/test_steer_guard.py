from __future__ import annotations

import json
from pathlib import Path

from aictx import cli
from aictx.mcp.server import handle_request
from aictx.mcp.tools import call_tool
from aictx.scaffold import init_repo_scaffold
from aictx.steer_guard import build_steer_guard


def _parser():
    return cli.build_parser()


def test_steer_side_comment_returns_ignore(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)

    payload = build_steer_guard(repo, message="just an idea for later")

    assert payload["status"] == "ok"
    assert payload["classification"] == "side_comment"
    assert payload["decision"] in {"ignore_as_side_comment", "continue"}


def test_steer_scope_constraint_updates_contract(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)

    payload = build_steer_guard(repo, message="don't touch src/auth.py", current_action="edit")

    assert payload["classification"] == "scope_constraint"
    assert payload["decision"] == "update_contract"
    assert payload["impact"] == "contract_update_required"
    assert payload["suggested_updates"]["forbidden_paths"] == ["src/auth.py"]


def test_steer_new_requirement_appends_requirement(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)

    payload = build_steer_guard(repo, message="also update docs")

    assert payload["classification"] == "new_requirement"
    assert payload["decision"] == "append_requirement"
    assert payload["suggested_updates"]["requirement_note"] == "also update docs"


def test_steer_validation_change_updates_validation(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)

    payload = build_steer_guard(repo, message="don't run the full suite")

    assert payload["classification"] == "validation_change"
    assert payload["decision"] == "update_validation"
    assert payload["impact"] == "validation_update_required"


def test_steer_cancellation_pauses(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)

    payload = build_steer_guard(repo, message="wait")

    assert payload["classification"] == "cancellation"
    assert payload["decision"] == "pause"
    assert payload["impact"] == "work_should_pause"


def test_steer_ambiguous_asks_user(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)

    payload = build_steer_guard(repo, message="hmm maybe")

    assert payload["classification"] == "unknown"
    assert payload["decision"] == "ask_user"


def test_steer_output_is_compact(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)

    payload = build_steer_guard(repo, message="be careful not to break login")

    assert set(payload) == {"status", "classification", "decision", "impact", "summary", "agent_instruction", "suggested_updates"}
    encoded = json.dumps(payload)
    assert "continuity_brief" not in encoded
    assert "loaded_context" not in encoded
    assert len(encoded) < 1200


def test_steer_is_read_only_by_default(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    before = {p.relative_to(repo).as_posix(): p.read_text(encoding="utf-8") for p in (repo / ".aictx").rglob("*") if p.is_file()}

    build_steer_guard(repo, message="also update docs")

    after = {p.relative_to(repo).as_posix(): p.read_text(encoding="utf-8") for p in (repo / ".aictx").rglob("*") if p.is_file()}
    assert after == before


def test_steer_cli_json(tmp_path: Path, capsys):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)

    args = _parser().parse_args(["steer", "--repo", str(repo), "--message", "don't touch src/auth.py", "--current-action", "edit", "--json"])
    assert args.func(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["classification"] == "scope_constraint"
    assert payload["decision"] == "update_contract"


def test_steer_mcp_readonly_tool_available_and_compact(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    tools = handle_request({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}, repo=str(repo), profile="readonly")
    specs = {tool["name"]: tool for tool in tools["result"]["tools"]}

    assert "aictx_steer_guard" in specs
    assert specs["aictx_steer_guard"]["inputSchema"]["required"] == ["message"]

    payload = call_tool("aictx_steer_guard", {"repo": str(repo), "message": "don't run the full suite"})
    assert payload["ok"] is True
    assert payload["classification"] == "validation_change"
    assert set(payload) >= {"ok", "status", "classification", "decision", "impact", "summary", "agent_instruction", "suggested_updates"}

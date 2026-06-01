from __future__ import annotations

import json
from pathlib import Path

from aictx import cli
from aictx.continuity_guard import build_continuity_guard
from aictx.contract_compliance import persist_resume_contract
from aictx.lifecycle import append_lifecycle_event
from aictx.mcp.server import handle_request
from aictx.mcp.tools import call_tool
from aictx.scaffold import init_repo_scaffold
from aictx.state import read_json, write_json
from aictx.work_state import start_work_state, work_state_paths


def _parser():
    return cli.build_parser()


def _persist_contract(repo: Path, *, task: str = "fix parser", primary: list[str] | None = None, test_command: str = "") -> None:
    primary = primary or ["src/parser.py"]
    persist_resume_contract(
        repo,
        {
            "generated_at": "2026-01-01T00:00:00Z",
            "request": task,
            "execution_contract": {
                "task_goal": task,
                "first_action": {"type": "open_file", "path": primary[0], "binding": "must_open_first"},
                "edit_scope": {"primary": primary, "secondary_if_needed": ["tests/test_parser.py"], "avoid": ["docs/**"]},
                "test_command": {"command": test_command},
            },
        },
        session_id="s1",
        agent_id="codex",
    )


def _quiet(monkeypatch):
    import aictx.continuity_guard as guard

    monkeypatch.setattr(guard, "build_continuity_quality_issues", lambda *a, **k: {"status": "ok", "issues": []})
    monkeypatch.setattr(guard, "build_lifecycle_status", lambda *a, **k: {"status": "ok", "warnings": [], "open_sessions": []})


def test_guard_before_first_edit_allows_aligned_contract(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    start_work_state(repo, "fix parser", initial={"active_files": ["src/parser.py"]})
    _persist_contract(repo)
    _quiet(monkeypatch)

    payload = build_continuity_guard(repo, action="before_first_edit", paths=["src/parser.py"], session_id="s1")

    assert payload["decision"] == "allow"
    assert payload["status"] == "ok"
    assert payload["warnings"] == []


def test_guard_edit_outside_scope_returns_caution(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    start_work_state(repo, "fix parser", initial={"active_files": ["src/parser.py"]})
    _persist_contract(repo)
    _quiet(monkeypatch)

    payload = build_continuity_guard(repo, action="edit", paths=["README.md"], session_id="s1")

    assert payload["decision"] == "caution"
    assert payload["checks"]["contract_alignment"] == "warning"
    assert any(item["code"] == "outside_expected_scope" for item in payload["warnings"])


def test_guard_final_boundaries_warn_when_validation_missing(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    start_work_state(repo, "fix parser")
    _persist_contract(repo, test_command="pytest tests/test_parser.py")
    _quiet(monkeypatch)

    final_answer = build_continuity_guard(repo, action="final_answer", session_id="s1")
    finalize = build_continuity_guard(repo, action="finalize", session_id="s1")

    assert final_answer["decision"] == "re_ground"
    assert finalize["decision"] == "re_ground"
    assert any(item["code"] == "validation_evidence_missing" for item in final_answer["warnings"])


def test_guard_stale_work_state_returns_reground(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    start_work_state(repo, "fix parser")
    active = read_json(work_state_paths(repo, "fix-parser")["thread"], {})
    active["updated_at"] = "2020-01-01T00:00:00Z"
    write_json(work_state_paths(repo, "fix-parser")["thread"], active)
    _quiet(monkeypatch)

    payload = build_continuity_guard(repo, action="continue_after_idle")

    assert payload["decision"] == "re_ground"
    assert payload["checks"]["work_state"] == "warning"


def test_guard_surfaces_quality_warning_compactly(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    start_work_state(repo, "fix parser")
    import aictx.continuity_guard as guard

    monkeypatch.setattr(guard, "build_continuity_quality_issues", lambda *a, **k: {"status": "warning", "issues": [{"code": "missing_validation_evidence", "severity": "warning", "summary": "Validation evidence is missing for carried continuity.", "loaded_items": [{"too": "large"}]}]})
    monkeypatch.setattr(guard, "build_lifecycle_status", lambda *a, **k: {"status": "ok", "warnings": [], "open_sessions": []})

    payload = build_continuity_guard(repo, action="edit", paths=["src/parser.py"])

    assert any(item["code"] == "missing_validation_evidence" for item in payload["warnings"])
    assert "loaded_items" not in json.dumps(payload)


def test_guard_surfaces_lifecycle_warning_compactly(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    start_work_state(repo, "fix parser")
    import aictx.continuity_guard as guard

    monkeypatch.setattr(guard, "build_continuity_quality_issues", lambda *a, **k: {"status": "ok", "issues": []})
    monkeypatch.setattr(guard, "build_lifecycle_status", lambda *a, **k: {"status": "warning", "warnings": [{"code": "session_started_but_not_finalized", "summary": "Session started with resume but finalize was not observed."}], "open_sessions": []})

    payload = build_continuity_guard(repo, action="continue_after_idle")

    assert payload["decision"] == "re_ground"
    assert payload["checks"]["lifecycle"] == "warning"


def test_guard_does_not_mutate_continuity_files(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    start_work_state(repo, "fix parser")
    append_lifecycle_event(repo, {"event_type": "resume_called", "timestamp": "2020-01-01T00:00:00Z", "task": "fix parser", "session_id": "s1"})
    before = {p.relative_to(repo).as_posix(): p.read_text(encoding="utf-8") for p in (repo / ".aictx").rglob("*") if p.is_file()}

    payload = build_continuity_guard(repo, action="final_answer", session_id="s1")

    after = {p.relative_to(repo).as_posix(): p.read_text(encoding="utf-8") for p in (repo / ".aictx").rglob("*") if p.is_file()}
    assert payload["status"] in {"ok", "warning", "error"}
    assert after == before




def test_guard_reuses_quality_within_process(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    start_work_state(repo, "fix parser", initial={"active_files": ["src/parser.py"]})
    _persist_contract(repo)
    import aictx.continuity_guard as guard

    guard._QUALITY_CACHE.clear()
    calls = {"count": 0}

    def quality(*args, **kwargs):
        calls["count"] += 1
        return {"status": "ok", "issues": []}

    monkeypatch.setattr(guard, "build_continuity_quality_issues", quality)
    monkeypatch.setattr(guard, "build_lifecycle_status", lambda *a, **k: {"status": "ok", "warnings": [], "open_sessions": []})

    first = build_continuity_guard(repo, action="edit", paths=["src/parser.py"], session_id="s1")
    second = build_continuity_guard(repo, action="edit", paths=["src/parser.py"], session_id="s1")

    assert first["decision"] == second["decision"] == "allow"
    assert calls["count"] == 1

def test_guard_cli_json(tmp_path: Path, capsys, monkeypatch):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    start_work_state(repo, "fix parser")
    _quiet(monkeypatch)

    args = _parser().parse_args(["guard", "--repo", str(repo), "--action", "edit", "--paths", "src/parser.py", "--intent", "fix parser", "--json"])
    assert args.func(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert set(payload) == {"status", "decision", "warnings", "checks", "suggested_next"}


def test_guard_mcp_readonly_tool_available_and_compact(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    tools = handle_request({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}, repo=str(repo), profile="readonly")
    specs = {tool["name"]: tool for tool in tools["result"]["tools"]}

    assert "aictx_continuity_guard" in specs
    assert specs["aictx_continuity_guard"]["inputSchema"]["required"] == ["action"]

    payload = call_tool("aictx_continuity_guard", {"repo": str(repo), "action": "final_answer"})
    assert payload["ok"] is True
    assert set(payload) >= {"ok", "status", "decision", "warnings", "checks", "suggested_next"}
    assert "continuity_brief" not in json.dumps(payload)

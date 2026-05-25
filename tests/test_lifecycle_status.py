from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from aictx import cli
from aictx.lifecycle import append_lifecycle_event, build_lifecycle_status
from aictx.scaffold import init_repo_scaffold
from aictx.state import read_jsonl, write_json
from aictx.work_state import start_work_state, work_state_paths

NOW = datetime(2026, 5, 25, 12, 0, tzinfo=timezone.utc)


def _event(repo: Path, event_type: str, **extra) -> None:
    append_lifecycle_event(repo, {"event_type": event_type, "timestamp": extra.pop("timestamp", "2026-05-25T08:00:00Z"), **extra})


def test_completed_session_has_ok_lifecycle(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    _event(repo, "resume_called", session_id="s1", task="fix parser")
    _event(repo, "finalize_called", timestamp="2026-05-25T08:30:00Z", session_id="s1", task="fix parser", status="success", commands_count=1)

    payload = build_lifecycle_status(repo, request_text="fix parser", session_id="s1", now=NOW)

    assert payload["status"] == "ok"
    assert payload["warnings"] == []


def test_incomplete_old_session_warns_but_recent_session_does_not(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    _event(repo, "resume_called", session_id="old", task="fix parser")
    _event(repo, "resume_called", timestamp="2026-05-25T11:00:00Z", session_id="recent", task="fix parser")

    payload = build_lifecycle_status(repo, request_text="fix parser", now=NOW)

    codes = {item["code"] for item in payload["warnings"]}
    assert "session_started_but_not_finalized" in codes
    assert {item["session_id"] for item in payload["warnings"]} == {"old"}


def test_unrelated_old_session_is_suppressed_for_current_request(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    _event(repo, "resume_called", session_id="s1", task="release docs")

    payload = build_lifecycle_status(repo, request_text="fix parser", now=NOW)

    assert payload["open_sessions"]
    assert payload["warnings"] == []


def test_open_contract_without_compliance_warns(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    _event(repo, "resume_called", session_id="s1", task="fix parser", contract_id="contract-1")

    payload = build_lifecycle_status(repo, request_text="fix parser", now=NOW)

    assert "contract_generated_not_evaluated" in {item["code"] for item in payload["warnings"]}


def test_finalize_changes_without_commands_or_tests_warns(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    _event(repo, "finalize_called", session_id="s1", task="fix parser", status="success", files_edited_count=1, commands_count=0, tests_count=0)

    payload = build_lifecycle_status(repo, request_text="fix parser", now=NOW)

    codes = {item["code"] for item in payload["warnings"]}
    assert "changes_without_evidence" in codes
    assert "validation_evidence_missing" in codes


def test_stale_active_work_state_warns(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    state = start_work_state(repo, "fix parser")
    state["updated_at"] = "2026-05-23T08:00:00Z"
    write_json(work_state_paths(repo, state["task_id"])["thread"], state)

    payload = build_lifecycle_status(repo, request_text="fix parser", now=NOW)

    assert "active_work_state_no_recent_finalization" in {item["code"] for item in payload["warnings"]}


def test_readonly_mcp_session_warns_when_not_finalized(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    _event(repo, "resume_called", source="mcp", session_id="s1", task="fix parser")

    payload = build_lifecycle_status(repo, request_text="fix parser", now=NOW)

    assert "readonly_mcp_only" in {item["code"] for item in payload["warnings"]}


def test_cli_resume_and_finalize_write_lifecycle_events(tmp_path: Path, capsys) -> None:
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    parser = cli.build_parser()

    resume = parser.parse_args(["resume", "--repo", str(repo), "--task", "fix parser", "--session-id", "s1", "--json"])
    assert resume.func(resume) == 0
    resumed = capsys.readouterr().out
    assert '"lifecycle_status"' in resumed

    finalize = parser.parse_args(["finalize", "--repo", str(repo), "--status", "success", "--summary", "done", "--task", "fix parser", "--session-id", "s1", "--commands-executed", "pytest", "--json"])
    assert finalize.func(finalize) == 0

    rows = read_jsonl(repo / ".aictx" / "continuity" / "lifecycle_events.jsonl")
    assert [row["event_type"] for row in rows][-2:] == ["resume_called", "finalize_called"]
    assert build_lifecycle_status(repo, request_text="fix parser", session_id="s1", now=NOW)["status"] == "ok"

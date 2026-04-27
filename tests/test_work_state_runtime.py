from __future__ import annotations

import json
import sys
from pathlib import Path

from aictx import cli
from aictx.middleware import finalize_execution, prepare_execution
from aictx.runtime_launcher import run_execution
from aictx.scaffold import init_repo_scaffold
from aictx.state import write_json
from aictx.work_state import load_work_state, start_work_state


def _payload(repo: Path, execution_id: str = "exec-work-state") -> dict:
    return {
        "repo_root": str(repo),
        "user_request": "continue work state task",
        "agent_id": "codex",
        "adapter_id": "codex",
        "execution_id": execution_id,
        "timestamp": "2026-04-27T10:00:00Z",
    }


def test_prepare_execution_exposes_active_work_state(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    start_work_state(repo, "Fix login token refresh", initial={"next_action": "inspect interceptor"})

    prepared = prepare_execution(_payload(repo))

    assert prepared["active_work_state"]["task_id"] == "fix-login-token-refresh"
    assert prepared["active_work_state"]["next_action"] == "inspect interceptor"
    assert prepared["continuity_context"]["active_work_state"]["goal"] == "Fix login token refresh"
    assert prepared["continuity_context"]["loaded"]["work_state"] is True


def test_prepare_execution_without_active_work_state_is_empty(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)

    prepared = prepare_execution(_payload(repo))

    assert prepared["active_work_state"] == {}
    assert "work_state" not in prepared["continuity_context"]["loaded"]


def test_finalize_execution_updates_active_work_state_conservatively(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    start_work_state(repo, "Fix login token refresh")
    prepared = prepare_execution({**_payload(repo), "files_opened": ["src/api/client.ts"], "commands_executed": ["pytest -q tests/test_auth.py"]})

    finalized = finalize_execution(prepared, {"success": True, "result_summary": "tests passed"})
    state = load_work_state(repo, "fix-login-token-refresh")

    assert finalized["work_state_updated"]["updated"] is True
    assert finalized["work_state_updated"]["task_id"] == "fix-login-token-refresh"
    assert "src/api/client.ts" in state["active_files"]
    assert "Command succeeded: pytest -q tests/test_auth.py" in state["verified"]
    assert "pytest -q tests/test_auth.py" in state["recommended_commands"]


def test_finalize_execution_with_failure_does_not_invent_verified(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    start_work_state(repo, "Fix login token refresh")
    prepared = prepare_execution({**_payload(repo), "commands_executed": ["pytest -q"], "notable_errors": ["AssertionError: token stale"]})

    finalize_execution(prepared, {"success": False, "result_summary": "test failed"})
    state = load_work_state(repo, "fix-login-token-refresh")

    assert state["verified"] == []
    assert "Observed error: AssertionError: token stale" in state["risks"]


def test_finalize_execution_accepts_explicit_work_state_patch(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    start_work_state(repo, "Fix login token refresh")
    prepared = prepare_execution(_payload(repo))

    finalized = finalize_execution(
        prepared,
        {
            "success": True,
            "result_summary": "preserved next action",
            "work_state": {"current_hypothesis": "token not persisted", "next_action": "run auth tests"},
        },
    )
    state = load_work_state(repo, "fix-login-token-refresh")

    assert finalized["work_state_updated"]["updated"] is True
    assert state["current_hypothesis"] == "token not persisted"
    assert state["next_action"] == "run auth tests"


def test_run_execution_propagates_work_state_json_and_records_success(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    start_work_state(repo, "Validate work state continuity")

    outcome = run_execution(
        {**_payload(repo, "exec-run-work-state"), "work_state": {"next_action": "review runtime update"}},
        [sys.executable, "-c", "print('ok')"],
    )
    state = load_work_state(repo, "validate-work-state-continuity")

    assert outcome["exit_code"] == 0
    assert outcome["finalized"]["work_state_updated"]["updated"] is True
    assert state["next_action"] == "review runtime update"
    assert any(item.startswith("Command succeeded:") for item in state["verified"])


def test_internal_cli_accepts_work_state_json_args() -> None:
    parser = cli.build_parser()
    prepare = parser.parse_args([
        "internal", "execution", "prepare", "--request", "x", "--agent-id", "codex", "--execution-id", "exec-1", "--work-state-json", '{"next_action":"x"}', "--work-state-file", "work-state.json",
    ])
    finalize = parser.parse_args([
        "internal", "execution", "finalize", "--prepared", "prepared.json", "--work-state-json", '{"next_action":"x"}', "--work-state-file", "work-state.json",
    ])
    run = parser.parse_args([
        "internal", "run-execution", "--request", "x", "--agent-id", "codex", "--work-state-json", '{"next_action":"x"}', "--work-state-file", "work-state.json", "--", sys.executable, "-c", "pass",
    ])

    assert prepare.work_state_json == '{"next_action":"x"}'
    assert prepare.work_state_file == "work-state.json"
    assert finalize.work_state_json == '{"next_action":"x"}'
    assert finalize.work_state_file == "work-state.json"
    assert run.work_state_json == '{"next_action":"x"}'
    assert run.work_state_file == "work-state.json"


def test_internal_finalize_accepts_work_state_file(tmp_path: Path, capsys) -> None:
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    start_work_state(repo, "Fix login token refresh")
    prepared = prepare_execution(_payload(repo, "exec-work-state-file"))
    prepared_path = tmp_path / "prepared.json"
    patch_path = tmp_path / "work-state.json"
    write_json(prepared_path, prepared)
    write_json(patch_path, {"unverified": ["manual auth flow"], "next_action": "run browser auth smoke"})

    parser = cli.build_parser()
    args = parser.parse_args([
        "internal", "execution", "finalize",
        "--prepared", str(prepared_path),
        "--success",
        "--result-summary", "preserved explicit work state file",
        "--work-state-file", str(patch_path),
    ])

    assert args.func(args) == 0
    finalized = json.loads(capsys.readouterr().out)
    state = load_work_state(repo, "fix-login-token-refresh")
    assert finalized["work_state_updated"]["updated"] is True
    assert state["unverified"] == ["manual auth flow"]
    assert state["next_action"] == "run browser auth smoke"

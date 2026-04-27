from __future__ import annotations

import json
from pathlib import Path

from aictx import cli
from aictx.scaffold import init_repo_scaffold


def test_task_parser_recognizes_subcommands() -> None:
    parser = cli.build_parser()

    args = parser.parse_args(["task", "start", "goal text"])
    assert args.task_command == "start"
    args = parser.parse_args(["task", "status"])
    assert args.task_command == "status"
    args = parser.parse_args(["task", "update", "--json-patch", '{"next_action":"x"}'])
    assert args.task_command == "update"
    args = parser.parse_args(["task", "list"])
    assert args.task_command == "list"
    args = parser.parse_args(["task", "show", "goal-text"])
    assert args.task_command == "show"
    args = parser.parse_args(["task", "resume", "goal-text"])
    assert args.task_command == "resume"
    args = parser.parse_args(["task", "close"])
    assert args.task_command == "close"


def test_task_status_json_reports_inactive_when_missing(tmp_path: Path, capsys) -> None:
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)

    parser = cli.build_parser()
    args = parser.parse_args(["task", "status", "--repo", str(repo), "--json"])
    assert args.func(args) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload == {"active": False}


def test_task_cli_flow_json_roundtrip(tmp_path: Path, capsys) -> None:
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    parser = cli.build_parser()

    start = parser.parse_args([
        "task", "start", "Fix login token refresh", "--repo", str(repo),
        "--initial-json", '{"current_hypothesis":"token not persisted","next_action":"inspect interceptor"}',
        "--json",
    ])
    assert start.func(start) == 0
    started = json.loads(capsys.readouterr().out)
    assert started["task_id"] == "fix-login-token-refresh"
    assert started["current_hypothesis"] == "token not persisted"

    status = parser.parse_args(["task", "status", "--repo", str(repo), "--json"])
    assert status.func(status) == 0
    active = json.loads(capsys.readouterr().out)
    assert active["active"] is True
    assert active["task_id"] == "fix-login-token-refresh"

    update = parser.parse_args([
        "task", "update", "--repo", str(repo),
        "--json-patch", '{"verified":["401 reproduces"],"recommended_commands":["npm test -- auth"]}',
        "--json",
    ])
    assert update.func(update) == 0
    updated = json.loads(capsys.readouterr().out)
    assert updated["verified"] == ["401 reproduces"]
    assert updated["recommended_commands"] == ["npm test -- auth"]
    assert updated["updated"] is True
    assert updated["changed_fields"] == ["recommended_commands", "verified"]

    close = parser.parse_args(["task", "close", "--repo", str(repo), "--status", "resolved", "--json"])
    assert close.func(close) == 0
    closed = json.loads(capsys.readouterr().out)
    assert closed["status"] == "resolved"

    final_status = parser.parse_args(["task", "status", "--repo", str(repo), "--json"])
    assert final_status.func(final_status) == 0
    inactive = json.loads(capsys.readouterr().out)
    assert inactive == {"active": False}


def test_task_status_human_output_is_compact(tmp_path: Path, capsys) -> None:
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    parser = cli.build_parser()

    start = parser.parse_args(["task", "start", "Fix login token refresh", "--repo", str(repo)])
    assert start.func(start) == 0
    output = capsys.readouterr().out.strip()
    assert output.startswith("Fix login token refresh.")

    update = parser.parse_args([
        "task", "update", "--repo", str(repo),
        "--json-patch", '{"next_action":"inspect interceptor ordering"}',
    ])
    assert update.func(update) == 0
    output = capsys.readouterr().out.strip()
    assert "Next: inspect interceptor ordering" in output


def test_task_list_show_resume_and_close_patch_cli(tmp_path: Path, capsys) -> None:
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    parser = cli.build_parser()

    start = parser.parse_args(["task", "start", "Fix login token refresh", "--repo", str(repo), "--json"])
    assert start.func(start) == 0
    capsys.readouterr()

    close = parser.parse_args([
        "task", "close", "--repo", str(repo), "--status", "blocked",
        "--json-patch", '{"risks":["waiting on flaky CI"],"next_action":"rerun CI"}',
        "--json",
    ])
    assert close.func(close) == 0
    closed = json.loads(capsys.readouterr().out)
    assert closed["status"] == "blocked"
    assert closed["risks"] == ["waiting on flaky CI"]
    assert closed["next_action"] == "rerun CI"

    listing = parser.parse_args(["task", "list", "--repo", str(repo), "--json"])
    assert listing.func(listing) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["tasks"][0]["task_id"] == "fix-login-token-refresh"
    assert payload["tasks"][0]["status"] == "blocked"

    show = parser.parse_args(["task", "show", "fix-login-token-refresh", "--repo", str(repo), "--json"])
    assert show.func(show) == 0
    shown = json.loads(capsys.readouterr().out)
    assert shown["task_id"] == "fix-login-token-refresh"

    resume = parser.parse_args(["task", "resume", "fix-login-token-refresh", "--repo", str(repo), "--json"])
    assert resume.func(resume) == 0
    resumed = json.loads(capsys.readouterr().out)
    assert resumed["status"] == "in_progress"

    status_all = parser.parse_args(["task", "status", "--repo", str(repo), "--all", "--json"])
    assert status_all.func(status_all) == 0
    all_payload = json.loads(capsys.readouterr().out)
    assert all_payload["tasks"][0]["active"] is True


def test_task_update_accepts_patch_from_file(tmp_path: Path, capsys) -> None:
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    patch_path = tmp_path / "patch.json"
    patch_path.write_text('{"next_action":"run targeted tests","unverified":["manual auth flow"]}', encoding="utf-8")
    parser = cli.build_parser()

    start = parser.parse_args(["task", "start", "Fix login token refresh", "--repo", str(repo)])
    assert start.func(start) == 0
    capsys.readouterr()

    update = parser.parse_args(["task", "update", "--repo", str(repo), "--from-file", str(patch_path), "--json"])
    assert update.func(update) == 0
    updated = json.loads(capsys.readouterr().out)

    assert updated["next_action"] == "run targeted tests"
    assert updated["unverified"] == ["manual auth flow"]
    assert updated["changed_fields"] == ["next_action", "unverified"]

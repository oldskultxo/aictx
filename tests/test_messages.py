from __future__ import annotations

import json
from pathlib import Path

from aictx import cli
from aictx.messages import get_message_mode, messages_muted, set_message_mode
from aictx.middleware import finalize_execution, prepare_execution
from aictx.scaffold import init_repo_scaffold


def _payload(repo: Path, execution_id: str = "exec-messages") -> dict:
    return {
        "repo_root": str(repo),
        "user_request": "implement messages controls",
        "agent_id": "codex",
        "adapter_id": "codex",
        "execution_id": execution_id,
        "timestamp": "2026-04-28T12:00:00Z",
        "files_opened": ["src/aictx/middleware.py"],
    }


def test_messages_default_unmuted(tmp_path: Path):
    repo = tmp_path / "repo"
    assert get_message_mode(repo) == "unmuted"
    assert messages_muted(repo) is False


def test_messages_mute_persists_repo_preference(tmp_path: Path):
    repo = tmp_path / "repo"
    payload = set_message_mode(repo, "muted")
    assert payload == {"messages": {"mode": "muted"}}
    assert get_message_mode(repo) == "muted"


def test_messages_unmute_persists_repo_preference(tmp_path: Path):
    repo = tmp_path / "repo"
    set_message_mode(repo, "muted")
    set_message_mode(repo, "unmuted")
    assert get_message_mode(repo) == "unmuted"


def test_invalid_message_mode_normalizes_to_unmuted(tmp_path: Path):
    repo = tmp_path / "repo"
    set_message_mode(repo, "invalid")
    assert get_message_mode(repo) == "unmuted"


def test_messages_cli_routes_to_expected_handlers():
    parser = cli.build_parser()
    mute = parser.parse_args(["messages", "mute", "--repo", "."])
    unmute = parser.parse_args(["messages", "unmute", "--repo", "."])
    status = parser.parse_args(["messages", "status", "--repo", ".", "--json"])

    assert mute.func == cli.cmd_messages_mute
    assert unmute.func == cli.cmd_messages_unmute
    assert status.func == cli.cmd_messages_status


def test_messages_cli_flow_human_and_json(tmp_path: Path, capsys):
    repo = tmp_path / "repo"
    parser = cli.build_parser()

    status = parser.parse_args(["messages", "status", "--repo", str(repo)])
    assert status.func(status) == 0
    assert capsys.readouterr().out.strip() == "AICTX messages: unmuted"
    assert not (repo / ".aictx" / "memory" / "user_preferences.json").exists()

    mute = parser.parse_args(["messages", "mute", "--repo", str(repo)])
    assert mute.func(mute) == 0
    assert capsys.readouterr().out.strip() == "AICTX messages: muted"

    status_json = parser.parse_args(["messages", "status", "--repo", str(repo), "--json"])
    assert status_json.func(status_json) == 0
    assert json.loads(capsys.readouterr().out) == {"messages": {"mode": "muted"}}

    unmute_json = parser.parse_args(["messages", "unmute", "--repo", str(repo), "--json"])
    assert unmute_json.func(unmute_json) == 0
    assert json.loads(capsys.readouterr().out) == {"messages": {"mode": "unmuted"}}

    status_again = parser.parse_args(["messages", "status", "--repo", str(repo)])
    assert status_again.func(status_again) == 0
    assert capsys.readouterr().out.strip() == "AICTX messages: unmuted"


def test_prepare_execution_suppresses_startup_banner_when_muted(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    set_message_mode(repo, "muted")

    prepared = prepare_execution(_payload(repo, "exec-muted-prepare"))

    assert prepared["startup_banner_text"] == ""
    assert prepared["startup_banner_policy"]["required"] is False
    assert prepared["startup_banner_policy"]["show_in_first_user_visible_response"] is False
    assert prepared["startup_banner_policy"]["muted"] is True
    assert prepared["message_visibility"]["mode"] == "muted"
    assert prepared["message_visibility"]["startup_banner_suppressed"] is True
    assert prepared["continuity_context"]
    assert prepared["continuity_context"]["startup_banner_text"]


def test_prepare_execution_defaults_to_unmuted_when_missing_preference(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)

    prepared = prepare_execution(_payload(repo, "exec-unmuted-prepare"))

    assert prepared["message_visibility"]["mode"] == "unmuted"
    assert prepared["message_visibility"]["startup_banner_suppressed"] is False
    assert prepared["startup_banner_policy"]["muted"] is False


def test_finalize_execution_suppresses_agent_summary_when_muted(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    set_message_mode(repo, "muted")

    prepared = prepare_execution(_payload(repo, "exec-muted-finalize"))
    finalized = finalize_execution(
        prepared,
        {
            "success": True,
            "result_summary": "done",
            "validated_learning": False,
            "decisions": [],
            "semantic_repo": [],
        },
    )

    assert finalized["agent_summary_text"] == ""
    assert finalized["message_visibility"]["mode"] == "muted"
    assert finalized["message_visibility"]["agent_summary_suppressed"] is True
    assert finalized["agent_summary"]
    assert finalized["continuity_value"] == finalized["agent_summary"]["continuity_value"]


def test_finalize_execution_defaults_to_unmuted_when_missing_preference(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)

    prepared = prepare_execution(_payload(repo, "exec-unmuted-finalize"))
    finalized = finalize_execution(
        prepared,
        {
            "success": True,
            "result_summary": "done",
            "validated_learning": False,
            "decisions": [],
            "semantic_repo": [],
        },
    )

    assert finalized["message_visibility"]["mode"] == "unmuted"
    assert "agent_summary_text" in finalized
    assert finalized["agent_summary_text"]


def test_muted_run_execution_keeps_command_output_but_hides_automatic_messages(tmp_path: Path, capsys):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    cli.prepare_repo_runtime(repo)
    set_message_mode(repo, "muted")
    parser = cli.build_parser()

    args = parser.parse_args(
        [
            "internal",
            "run-execution",
            "--repo",
            str(repo),
            "--request",
            "run wrapped command while muted",
            "--agent-id",
            "codex",
            "--execution-id",
            "exec-muted-run",
            "--",
            "python3",
            "-c",
            "print('wrapped ok')",
        ]
    )

    assert args.func(args) == 0
    output = capsys.readouterr().out
    assert "wrapped ok" in output
    assert "AICTX summary:" not in output
    assert f"codex@{repo.name} (session #1) - despierto" not in output

from __future__ import annotations

import json
from pathlib import Path

from aictx import cli
from aictx.continuity import DECISIONS_PATH, HANDOFF_PATH
from aictx.scaffold import init_repo_scaffold
from aictx.state import write_json
from aictx.work_state import close_work_state, start_work_state


def test_next_command_prints_compact_human_guidance(tmp_path: Path, capsys):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    (repo / "src/aictx").mkdir(parents=True)
    (repo / "src/aictx/continuity.py").write_text("", encoding="utf-8")
    write_json(repo / HANDOFF_PATH, {
        "summary": "Continue next command.",
        "next_steps": ["wire CLI output"],
        "recommended_starting_points": ["src/aictx/continuity.py"],
    })
    (repo / DECISIONS_PATH).write_text(json.dumps({
        "decision": "Keep next output compact.",
        "related_paths": ["src/aictx/continuity.py"],
    }) + "\n", encoding="utf-8")

    parser = cli.build_parser()
    args = parser.parse_args(["next", "--repo", str(repo), "--request", "continue next command", "--files-opened", "src/aictx/continuity.py"])
    assert args.func(args) == 0

    output = capsys.readouterr().out
    assert output.startswith("AICTX next\n")
    assert "Continue:" in output
    assert "- wire CLI output" in output
    assert "Why:" in output
    assert "decisions:" in output


def test_next_command_json_exposes_brief(tmp_path: Path, capsys):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    parser = cli.build_parser()
    args = parser.parse_args(["next", "--repo", str(repo), "--json"])
    assert args.func(args) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["continuity_brief"]["version"] == 2
    assert "why_loaded" in payload


def test_next_command_prioritizes_active_work_state(tmp_path: Path, capsys):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    start_work_state(
        repo,
        "Fix login token refresh",
        initial={
            "current_hypothesis": "refresh retries before token update",
            "next_action": "inspect src/api/client.ts",
            "recommended_commands": ["npm test -- auth"],
        },
    )

    parser = cli.build_parser()
    args = parser.parse_args(["next", "--repo", str(repo), "--json"])
    assert args.func(args) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["continuity_brief"]["active_work_state"]["goal"] == "Fix login token refresh"
    assert payload["continuity_brief"]["where_to_continue"] == ["inspect src/api/client.ts"]

    args = parser.parse_args(["next", "--repo", str(repo)])
    assert args.func(args) == 0
    output = capsys.readouterr().out
    assert "Active work:" in output
    assert "- Goal: Fix login token refresh" in output
    assert "- Next: inspect src/api/client.ts" in output
    assert "- Verify: npm test -- auth" in output


def test_next_command_shows_recent_paused_or_blocked_work_when_no_active_task(tmp_path: Path, capsys):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    start_work_state(
        repo,
        "Fix login token refresh",
        initial={
            "current_hypothesis": "refresh retries before token update",
            "next_action": "rerun CI",
            "recommended_commands": ["npm test -- auth"],
        },
    )
    close_work_state(repo, status="blocked")

    parser = cli.build_parser()
    args = parser.parse_args(["next", "--repo", str(repo), "--json"])
    assert args.func(args) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["continuity_brief"]["active_work_state"] == {}
    assert payload["continuity_brief"]["recent_work_state"]["task_id"] == "fix-login-token-refresh"
    assert payload["continuity_brief"]["recent_work_state"]["status"] == "blocked"

    args = parser.parse_args(["next", "--repo", str(repo)])
    assert args.func(args) == 0
    output = capsys.readouterr().out
    assert "Recent paused/blocked work:" in output
    assert "- Goal: Fix login token refresh (blocked)" in output
    assert "- Next: rerun CI" in output

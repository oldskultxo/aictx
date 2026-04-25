from __future__ import annotations

import json
from pathlib import Path

from aictx import cli
from aictx.continuity import DECISIONS_PATH, HANDOFF_PATH
from aictx.scaffold import init_repo_scaffold
from aictx.state import write_json


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

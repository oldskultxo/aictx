from __future__ import annotations

import json
from pathlib import Path

import pytest

from aictx import cli
from aictx.continuity import DECISIONS_PATH, HANDOFF_PATH, RESUME_CAPSULE_JSON_PATH, RESUME_CAPSULE_MARKDOWN_PATH
from aictx.repo_map.config import write_repomap_config, write_repomap_index
from aictx.scaffold import init_repo_scaffold
from aictx.state import write_json
from aictx.work_state import close_work_state, start_work_state


def _parser():
    return cli.build_parser()


def _seed_repomap(repo: Path) -> None:
    (repo / "src/aictx").mkdir(parents=True)
    (repo / "src/aictx/continuity.py").write_text("def build_resume_capsule():\n    pass\n", encoding="utf-8")
    (repo / "tests").mkdir()
    (repo / "tests/test_resume_command.py").write_text("def test_resume():\n    pass\n", encoding="utf-8")
    write_repomap_config(repo, {"enabled": True})
    write_repomap_index(
        repo,
        {
            "version": 1,
            "provider": "tree_sitter",
            "mode": "full",
            "files": [
                {
                    "path": "src/aictx/continuity.py",
                    "language": "python",
                    "symbols": [{"name": "build_resume_capsule", "kind": "function", "line": 1, "language": "python"}],
                    "imports": [],
                    "metadata_only": False,
                    "provider": "tree_sitter",
                    "reason": "",
                    "size_bytes": 10,
                },
                {
                    "path": "tests/test_resume_command.py",
                    "language": "python",
                    "symbols": [{"name": "test_resume", "kind": "function", "line": 1, "language": "python"}],
                    "imports": [],
                    "metadata_only": False,
                    "provider": "tree_sitter",
                    "reason": "",
                    "size_bytes": 10,
                },
            ],
        },
    )


def test_resume_default_markdown_and_budget(tmp_path: Path, capsys):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)

    args = _parser().parse_args(["resume", "--repo", str(repo), "--request", "implement resume capsule"])
    assert args.func(args) == 0

    output = capsys.readouterr().out
    assert output.startswith("AICTX continuity capsule\n")
    assert "Current request" in output
    assert "Avoid" in output
    assert len(output) <= 6000
    assert (repo / RESUME_CAPSULE_MARKDOWN_PATH).exists()
    assert (repo / RESUME_CAPSULE_JSON_PATH).exists()


def test_resume_json_schema_and_written_files(tmp_path: Path, capsys):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)

    args = _parser().parse_args(["resume", "--repo", str(repo), "--request", "resume command", "--json"])
    assert args.func(args) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["schema_version"] == "1.0"
    assert payload["mode"] == "agent_brief"
    assert payload["request"] == "resume command"
    assert payload["task_state"]["status"] in {"active", "completed", "blocked", "unknown"}
    assert payload["written_files"] == {
        "markdown": ".aictx/continuity/resume_capsule.md",
        "json": ".aictx/continuity/resume_capsule.json",
    }
    assert json.loads((repo / RESUME_CAPSULE_JSON_PATH).read_text(encoding="utf-8"))["schema_version"] == "1.0"


def test_resume_full_has_more_detail_than_default(tmp_path: Path, capsys):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    (repo / DECISIONS_PATH).write_text(
        "\n".join(json.dumps({"decision": f"Decision {i}", "related_paths": []}) for i in range(6)) + "\n",
        encoding="utf-8",
    )

    parser = _parser()
    assert parser.parse_args(["resume", "--repo", str(repo), "--request", "decision", "--json"]).func(
        parser.parse_args(["resume", "--repo", str(repo), "--request", "decision", "--json"])
    ) == 0
    compact = json.loads(capsys.readouterr().out)
    assert parser.parse_args(["resume", "--repo", str(repo), "--request", "decision", "--json", "--full"]).func(
        parser.parse_args(["resume", "--repo", str(repo), "--request", "decision", "--json", "--full"])
    ) == 0
    full = json.loads(capsys.readouterr().out)

    assert len(full["capsule"]["decisions"]) > len(compact["capsule"]["decisions"])


def test_resume_active_work_state_drives_task_state(tmp_path: Path, capsys):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    start_work_state(
        repo,
        "Implement resume command",
        initial={"next_action": "inspect src/aictx/continuity.py", "active_files": ["src/aictx/continuity.py"]},
    )
    (repo / "src/aictx").mkdir(parents=True)
    (repo / "src/aictx/continuity.py").write_text("", encoding="utf-8")

    args = _parser().parse_args(["resume", "--repo", str(repo), "--request", "resume", "--json"])
    assert args.func(args) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["task_state"]["status"] == "active"
    assert payload["task_state"]["confidence"] == "high"
    assert payload["capsule"]["next_action"] == "inspect src/aictx/continuity.py"


def test_resume_completed_previous_task_is_background(tmp_path: Path, capsys):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    start_work_state(repo, "Old task", initial={"next_action": "done"})
    close_work_state(repo, status="resolved")
    write_json(repo / HANDOFF_PATH, {"summary": "Old task finished.", "completed": ["done"], "recommended_starting_points": []})

    args = _parser().parse_args(["resume", "--repo", str(repo), "--request", "new task", "--json"])
    assert args.func(args) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["task_state"]["status"] == "completed"
    assert "background" in payload["capsule"]["resuming"]


def test_resume_missing_entry_point_lowers_confidence_and_uses_fallback(tmp_path: Path, capsys):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    _seed_repomap(repo)
    write_json(
        repo / HANDOFF_PATH,
        {
            "summary": "Continue resume command.",
            "recommended_starting_points": ["src/aictx/missing.py"],
        },
    )

    args = _parser().parse_args(["resume", "--repo", str(repo), "--request", "build resume capsule", "--json"])
    assert args.func(args) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["task_state"]["confidence"] in {"low", "medium"}
    assert "missing_entry_point:src/aictx/missing.py" in payload["warnings"]
    assert payload["capsule"]["entry_points"]


def test_resume_repomap_slice_has_primary_and_secondary(tmp_path: Path, capsys):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    _seed_repomap(repo)

    args = _parser().parse_args(["resume", "--repo", str(repo), "--request", "resume command test", "--json"])
    assert args.func(args) == 0

    repo_map = json.loads(capsys.readouterr().out)["capsule"]["repo_map"]
    assert repo_map["primary"][0]["path"] == "src/aictx/continuity.py"
    assert repo_map["secondary"]


def test_advanced_help_lists_advanced_commands(capsys):
    with pytest.raises(SystemExit) as exc:
        _parser().parse_args(["advanced", "--help"])
    assert exc.value.code == 0
    output = capsys.readouterr().out
    for command in ["suggest", "reuse", "next", "task", "messages", "map", "report", "internal"]:
        assert command in output


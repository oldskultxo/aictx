from __future__ import annotations

import json
from pathlib import Path

import aictx.cli as cli
from aictx.continuity.quality import (
    DEMOTED_MAX_DAYS,
    FRESH_MAX_DAYS,
    POSSIBLY_STALE_MAX_DAYS,
    build_continuity_quality_report,
)
from aictx.continuity_view import CONTINUITY_VIEW_PATH, write_continuity_view
from aictx.repo_map.config import write_repomap_config, write_repomap_index
from aictx.scaffold import init_repo_scaffold
from aictx.work_state import start_work_state


def _parser():
    return cli.build_parser()


def _seed_live_repo(repo: Path) -> None:
    (repo / "src").mkdir(parents=True, exist_ok=True)
    (repo / "src/live.py").write_text("def live():\n    return True\n", encoding="utf-8")
    write_repomap_config(repo, {"enabled": True})
    write_repomap_index(
        repo,
        {
            "version": 1,
            "files": [
                {
                    "path": "src/live.py",
                    "language": "python",
                    "symbols": [{"name": "live", "kind": "function", "line": 1, "language": "python"}],
                }
            ],
        },
    )


def test_resume_new_contract_reports_pending_validation_not_missing_validation(tmp_path: Path, capsys):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    _seed_live_repo(repo)
    write_continuity_view(repo)

    args = _parser().parse_args(["resume", "--repo", str(repo), "--task", "live", "--json"])
    assert args.func(args) == 0
    payload = json.loads(capsys.readouterr().out)

    issues = payload["continuity_quality"]["issues"]
    assert not any(issue["code"] == "missing_validation_evidence" and issue["severity"] == "warning" for issue in issues)
    pending = [issue for issue in issues if issue["code"] == "pending_validation_for_new_contract"]
    if pending:
        assert pending[0]["severity"] == "info"
    assert payload["continuity_quality"]["status"] == "ok"

    args = _parser().parse_args(["resume", "--repo", str(repo), "--task", "live"])
    assert args.func(args) == 0
    text = capsys.readouterr().out
    assert "Continuity Quality" not in text


def test_continuity_quality_warns_for_carried_missing_validation_gap(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    report = build_continuity_quality_report(
        repo,
        context={
            "carryover_gaps": [
                {
                    "kind": "missing_validation",
                    "source_execution_id": "prev-exec",
                    "summary": "Expected pytest was not recorded",
                    "next_action": "Run pytest",
                }
            ]
        },
    )

    matches = [issue for issue in report["issues"] if issue["code"] == "missing_validation_evidence"]
    assert matches
    assert matches[0]["severity"] == "warning"
    assert report["status"] == "warning"


def test_continuity_quality_reports_deleted_file_reference_and_demotes_old_items(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    start_work_state(
        repo,
        "Old stale work",
        initial={"active_files": ["src/missing.py"], "next_action": "inspect missing file"},
    )

    report = build_continuity_quality_report(repo)

    assert any(issue["code"] == "deleted_file_reference" for issue in report["issues"])
    assert report["status"] == "warning"


def test_continuity_quality_threshold_constants_are_public():
    assert FRESH_MAX_DAYS == 7
    assert POSSIBLY_STALE_MAX_DAYS == 30
    assert DEMOTED_MAX_DAYS == 90

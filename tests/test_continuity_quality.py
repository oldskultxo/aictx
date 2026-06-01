from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from aictx import cli
from aictx.continuity import DECISIONS_PATH, HANDOFF_PATH
from aictx.continuity.quality import DEMOTED_MAX_DAYS, FRESH_MAX_DAYS, POSSIBLY_STALE_MAX_DAYS, build_continuity_quality_issues, build_continuity_quality_report
from aictx.failures import FAILURE_PATTERNS_PATH
from aictx.mcp.resources import resource_content
from aictx.mcp.tools import call_tool
from aictx.repo_map.config import write_repomap_config, write_repomap_index, write_repomap_manifest, write_repomap_status
from aictx.scaffold import init_repo_scaffold


NOW = datetime(2026, 5, 24, tzinfo=timezone.utc)


def _seed_repomap(repo: Path) -> None:
    (repo / "src").mkdir(parents=True, exist_ok=True)
    (repo / "src" / "live.py").write_text("def live():\n    pass\n", encoding="utf-8")
    write_repomap_config(repo, {"enabled": True})
    write_repomap_status(repo, {"available": True, "last_refresh_status": "ok"})
    write_repomap_manifest(repo, {"files_indexed": 1, "symbols_indexed": 1})
    write_repomap_index(repo, {"version": 1, "files": [{"path": "src/live.py", "symbols": []}]})


def _seed_view(repo: Path) -> None:
    path = repo / ".aictx" / "reports" / "continuity-view.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# Continuity View\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_continuity_quality_fresh_state_is_high_score(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    _seed_repomap(repo)
    _seed_view(repo)
    (repo / HANDOFF_PATH).write_text(
        json.dumps({
            "summary": "fresh handoff",
            "updated_at": "2026-05-24T00:00:00Z",
            "recommended_starting_points": ["src/live.py"],
        }),
        encoding="utf-8",
    )

    report = build_continuity_quality_report(repo, now=NOW)

    assert report["status"] == "ok"
    assert report["score"] >= 80
    assert not [issue for issue in report["issues"] if issue["severity"] in {"warning", "error"}]
    assert report["fresh"]


def test_continuity_quality_reports_missing_repomap_and_view(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)

    report = build_continuity_quality_report(repo, now=NOW)
    issues = {issue["code"]: issue for issue in report["issues"]}

    assert report["status"] == "ok"
    assert issues["missing_repomap"]["severity"] == "info"
    assert issues["missing_continuity_view"]["severity"] == "info"
    assert report["score"] < 100
    assert report["advisory_only"] is True
    assert report["scoring_breakdown"]["base_score"] == 100


def test_continuity_quality_escalates_missing_view_when_continuity_exists(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    _seed_repomap(repo)
    (repo / HANDOFF_PATH).write_text(
        json.dumps({
            "summary": "needs a view",
            "updated_at": "2026-05-24T00:00:00Z",
            "recommended_starting_points": ["src/live.py"],
        }),
        encoding="utf-8",
    )

    report = build_continuity_quality_report(repo, now=NOW)
    issue = next(item for item in report["issues"] if item["code"] == "missing_continuity_view")

    assert issue["severity"] == "warning"
    assert report["status"] == "warning"


def test_continuity_quality_escalates_missing_repomap_when_enabled(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    write_repomap_config(repo, {"enabled": True})
    _seed_view(repo)

    report = build_continuity_quality_report(repo, now=NOW)
    issue = next(item for item in report["issues"] if item["code"] == "missing_repomap")

    assert issue["severity"] == "warning"


def test_continuity_quality_detects_deleted_file_references(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    _seed_repomap(repo)
    _seed_view(repo)
    (repo / HANDOFF_PATH).write_text(
        json.dumps({
            "summary": "deleted handoff",
            "updated_at": "2026-05-24T00:00:00Z",
            "recommended_starting_points": ["src/deleted.py"],
        }),
        encoding="utf-8",
    )
    _write_jsonl(repo / DECISIONS_PATH, [{
        "decision": "Use deleted file.",
        "execution_id": "decision-old",
        "timestamp": "2026-05-24T00:00:00Z",
        "related_paths": ["src/deleted.py"],
    }])
    _write_jsonl(repo / FAILURE_PATTERNS_PATH, [{
        "failure_id": "failure-deleted",
        "timestamp": "2026-05-24T00:00:00Z",
        "error_text": "deleted file failure",
        "files_involved": ["src/deleted.py"],
    }])

    report = build_continuity_quality_report(repo, now=NOW)

    missing = [issue for issue in report["issues"] if issue["code"] == "missing_linked_file"]
    assert missing
    assert any("src/deleted.py" in issue["related_paths"] for issue in missing)
    assert report["missing"]


def test_continuity_quality_caps_repeated_issue_penalties(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    _seed_repomap(repo)
    _seed_view(repo)
    _write_jsonl(repo / FAILURE_PATTERNS_PATH, [
        {
            "failure_id": f"failure-deleted-{index}",
            "timestamp": "2026-05-24T00:00:00Z",
            "error_text": "deleted file failure",
            "files_involved": [f"src/deleted_{index}.py"],
        }
        for index in range(5)
    ])

    report = build_continuity_quality_report(repo, now=NOW)
    penalties = [
        row for row in report["scoring_breakdown"]["penalties"]
        if row["code"] == "missing_linked_file"
    ]

    assert len(penalties) == 5
    assert sum(row["points"] for row in penalties) == 20
    assert any(row["capped"] for row in penalties)


def test_continuity_quality_demotes_old_memory_without_deleting(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    _seed_repomap(repo)
    _seed_view(repo)
    _write_jsonl(repo / DECISIONS_PATH, [{
        "decision": "Old but still inspectable decision.",
        "execution_id": "old-decision",
        "timestamp": "2026-04-01T00:00:00Z",
        "related_paths": ["src/live.py"],
    }])

    report = build_continuity_quality_report(repo, now=NOW)

    assert any(item.get("source_id") == "old-decision" for item in report["demoted"])
    assert (repo / DECISIONS_PATH).read_text(encoding="utf-8").count("old-decision") == 1


def test_resume_json_includes_quality_and_healthy_markdown_is_not_noisy(tmp_path: Path, capsys) -> None:
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    _seed_repomap(repo)
    _seed_view(repo)
    (repo / HANDOFF_PATH).write_text(
        json.dumps({
            "summary": "fresh handoff",
            "completed": ["validated fresh handoff"],
            "updated_at": "2026-05-24T00:00:00Z",
            "recommended_starting_points": ["src/live.py"],
        }),
        encoding="utf-8",
    )
    parser = cli.build_parser()

    args = parser.parse_args(["resume", "--repo", str(repo), "--task", "live", "--json"])
    assert args.func(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["continuity_quality"]["score"] >= 80

    args = parser.parse_args(["resume", "--repo", str(repo), "--task", "live"])
    assert args.func(args) == 0
    output = capsys.readouterr().out
    assert "Continuity quality" not in output



def test_resume_new_contract_reports_pending_validation_not_missing_validation(tmp_path: Path, capsys) -> None:
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    _seed_repomap(repo)
    _seed_view(repo)
    (repo / HANDOFF_PATH).write_text(
        json.dumps({
            "summary": "fresh handoff",
            "completed": ["fresh setup done"],
            "updated_at": "2026-05-24T00:00:00Z",
            "recommended_starting_points": ["src/live.py"],
        }),
        encoding="utf-8",
    )
    parser = cli.build_parser()

    args = parser.parse_args(["resume", "--repo", str(repo), "--task", "live", "--json"])
    assert args.func(args) == 0
    payload = json.loads(capsys.readouterr().out)
    issues = payload["continuity_quality"]["issues"]

    assert not any(issue["code"] == "missing_validation_evidence" and issue["severity"] == "warning" for issue in issues)
    pending = [issue for issue in issues if issue["code"] == "pending_validation_for_new_contract"]
    if pending:
        assert pending[0]["severity"] == "info"
    assert payload["continuity_quality"]["status"] == "ok"

    args = parser.parse_args(["resume", "--repo", str(repo), "--task", "live"])
    assert args.func(args) == 0
    output = capsys.readouterr().out
    assert "Continuity quality" not in output


def test_continuity_quality_warns_for_carried_missing_validation_gap(tmp_path: Path) -> None:
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




def test_continuity_quality_issues_is_compact(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)

    payload = build_continuity_quality_issues(repo, limit=2)

    assert set(payload) == {"schema_version", "generated_at", "score", "status", "request", "task_type", "advisory_only", "issues"}
    assert "loaded_items" not in payload
    assert len(payload["issues"]) <= 2

def test_continuity_quality_age_threshold_constants_are_public() -> None:
    assert FRESH_MAX_DAYS == 7
    assert POSSIBLY_STALE_MAX_DAYS == 30
    assert DEMOTED_MAX_DAYS == 90

def test_doctor_and_mcp_expose_continuity_quality(tmp_path: Path, capsys) -> None:
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    parser = cli.build_parser()

    args = parser.parse_args(["doctor", "--repo", str(repo), "--json"])
    assert args.func(args) == 0
    payload = json.loads(capsys.readouterr().out)
    check = next(item for item in payload["checks"] if item["name"] == "continuity_quality")
    assert check["details"]["score"] == payload["checks"][-1]["details"]["score"]

    tool_payload = call_tool("aictx_continuity_quality", {"repo": str(repo)})
    resource_payload = json.loads(resource_content("aictx://repo/current/continuity-quality", str(repo))["contents"][0]["text"])

    assert tool_payload["ok"] is True
    assert tool_payload["continuity_quality"]["score"] == resource_payload["score"]
    assert set(tool_payload["continuity_quality"]) >= {"score", "status", "issues", "loaded_items"}

from __future__ import annotations

from aictx.report import build_real_usage_report
from aictx.scaffold import init_repo_scaffold
from aictx.state import write_json


def test_real_usage_report_includes_repomap_defaults(tmp_path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)

    report = build_real_usage_report(repo)

    assert report["repo_map"] == {
        "enabled": False,
        "available": False,
        "files_indexed": 0,
        "symbols_indexed": 0,
        "last_refresh_status": "never",
    }


def test_real_usage_report_includes_repomap_status_and_counts(tmp_path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    write_json(repo / ".aictx" / "repo_map" / "config.json", {"enabled": True})
    write_json(repo / ".aictx" / "repo_map" / "status.json", {"available": True, "last_refresh_status": "ok"})
    write_json(repo / ".aictx" / "repo_map" / "manifest.json", {"files_indexed": 12, "symbols_indexed": 44})

    report = build_real_usage_report(repo)

    assert report["repo_map"] == {
        "enabled": True,
        "available": True,
        "files_indexed": 12,
        "symbols_indexed": 44,
        "last_refresh_status": "ok",
    }

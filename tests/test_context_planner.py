from __future__ import annotations

from pathlib import Path

from aictx.context_planner import build_structural_entry_points
from aictx.repo_map.config import write_repomap_config, write_repomap_index
from aictx.scaffold import init_repo_scaffold


def _seed_repomap(repo: Path) -> None:
    (repo / "src/aictx/middleware").mkdir(parents=True, exist_ok=True)
    (repo / "src/aictx/middleware/__init__.py").write_text("def prepare_execution():\n    pass\n\ndef prepare_repo_map_status():\n    pass\n", encoding="utf-8")
    (repo / "src/aictx/repo_map").mkdir(parents=True, exist_ok=True)
    (repo / "src/aictx/repo_map/query.py").write_text("def query_repo_map():\n    pass\n", encoding="utf-8")
    write_repomap_config(repo, {"enabled": True})
    write_repomap_index(
        repo,
        {
            "version": 1,
            "files": [
                {
                    "path": "src/aictx/middleware/__init__.py",
                    "language": "python",
                    "symbols": [
                        {"name": "prepare_execution", "kind": "function", "line": 1, "language": "python"},
                        {"name": "prepare_repo_map_status", "kind": "function", "line": 4, "language": "python"},
                    ],
                },
                {
                    "path": "src/aictx/repo_map/query.py",
                    "language": "python",
                    "symbols": [{"name": "query_repo_map", "kind": "function", "line": 1, "language": "python"}],
                },
            ],
        },
    )


def test_context_planner_returns_empty_when_no_repomap_index_exists(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    write_repomap_config(repo, {"enabled": True})

    assert build_structural_entry_points(repo, "improve prepare execution repo map status") == []


def test_context_planner_normalizes_repomap_query_results(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    _seed_repomap(repo)

    entries = build_structural_entry_points(repo, "improve prepare execution repo map status")

    assert entries
    assert entries[0]["kind"] == "structural_entry_point"
    assert entries[0]["path"] == "src/aictx/middleware/__init__.py"
    assert "prepare_execution" in entries[0]["symbols"]
    assert "prepare_repo_map_status" in entries[0]["symbols"]
    assert entries[0]["source"] == "repo_map"
    assert entries[0]["reasons"]

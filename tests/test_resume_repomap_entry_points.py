from __future__ import annotations

from pathlib import Path

from aictx.continuity import build_resume_capsule, render_resume_capsule
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


def test_resume_json_includes_structural_entry_points_and_expected_first_files(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    _seed_repomap(repo)

    payload = build_resume_capsule(repo, request_text="improve prepare execution repo map status", agent_id="codex")

    assert payload["structural_context"]["source"] == "repo_map"
    assert payload["structural_context"]["used"] is True
    assert payload["structural_entry_points"]
    assert payload["structural_entry_points"][0]["path"] == "src/aictx/middleware/__init__.py"
    assert payload["execution_contract"]["expected_first_files"][:1] == ["src/aictx/middleware/__init__.py"]
    assert payload["execution_contract"]["expected_first_files_source"] == "repo_map"
    assert len(payload["execution_contract"]["expected_first_files"]) <= 3


def test_text_resume_renders_structural_entry_points(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    _seed_repomap(repo)

    payload = build_resume_capsule(repo, request_text="improve prepare execution repo map status", agent_id="codex")
    text = render_resume_capsule(payload)

    assert "Structural entry points" in text
    assert "src/aictx/middleware/__init__.py" in text
    assert "symbols: prepare_execution, prepare_repo_map_status" in text


def test_resume_structural_entry_points_empty_when_repomap_disabled(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)

    payload = build_resume_capsule(repo, request_text="improve prepare execution repo map status", agent_id="codex")

    assert payload["structural_entry_points"] == []
    assert payload["structural_context"]["enabled"] is False
    assert payload["structural_context"]["used"] is False
    assert "expected_first_files" not in payload["execution_contract"]

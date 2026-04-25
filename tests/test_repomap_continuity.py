from __future__ import annotations

import json
from pathlib import Path

from aictx import cli
from aictx.continuity import HANDOFF_PATH, load_continuity_context
from aictx.repo_map.config import write_repomap_config, write_repomap_index
from aictx.scaffold import init_repo_scaffold
from aictx.state import write_json


def _seed_repomap(repo: Path) -> None:
    (repo / "src" / "aictx").mkdir(parents=True)
    (repo / "src" / "aictx" / "continuity.py").write_text("def render_startup_banner():\n    pass\n", encoding="utf-8")
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
                    "symbols": [{"name": "render_startup_banner", "kind": "function", "line": 1, "language": "python"}],
                    "imports": [],
                    "metadata_only": False,
                    "provider": "tree_sitter",
                    "reason": "",
                    "size_bytes": 10,
                }
            ],
        },
    )


def test_repomap_query_result_appears_in_ranked_items(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    _seed_repomap(repo)

    context = load_continuity_context(repo, request_text="startup banner")

    repo_map_items = [item for item in context["ranked_items"] if item["kind"] == "repo_map"]
    assert repo_map_items
    assert repo_map_items[0]["paths"] == ["src/aictx/continuity.py"]
    assert "repo_map:symbol_match" in repo_map_items[0]["reasons"]


def test_repomap_why_loaded_exists_when_map_contributes(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    _seed_repomap(repo)

    context = load_continuity_context(repo, request_text="startup banner")

    assert "repo_map" in context["why_loaded"]
    assert "repo_map:symbol_match" in context["why_loaded"]["repo_map"]


def test_continuity_brief_probable_paths_include_repomap_path(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    _seed_repomap(repo)

    context = load_continuity_context(repo, request_text="startup banner")

    assert "src/aictx/continuity.py" in context["continuity_brief"]["probable_paths"]


def test_next_json_includes_repomap_ranked_item(tmp_path: Path, capsys):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    _seed_repomap(repo)

    parser = cli.build_parser()
    args = parser.parse_args(["next", "--repo", str(repo), "--request", "startup banner", "--json"])
    assert args.func(args) == 0

    payload = json.loads(capsys.readouterr().out)
    assert any(item["kind"] == "repo_map" for item in payload["ranked_items"])
    assert "src/aictx/continuity.py" in payload["continuity_brief"]["probable_paths"]


def test_repomap_unavailable_keeps_existing_continuity_behavior(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    write_repomap_config(repo, {"enabled": True})

    context = load_continuity_context(repo, request_text="startup banner")

    assert not any(item["kind"] == "repo_map" for item in context["ranked_items"])
    assert context["why_loaded"]["repo_map"] == ["not_loaded"]


def test_repomap_ranked_items_are_capped_in_continuity_context(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    write_repomap_config(repo, {"enabled": True})
    records = []
    for index in range(5):
        path = f"src/startup_{index}.py"
        (repo / path).parent.mkdir(parents=True, exist_ok=True)
        (repo / path).write_text("def render_startup_banner():\n    pass\n", encoding="utf-8")
        records.append(
            {
                "path": path,
                "language": "python",
                "symbols": [{"name": "render_startup_banner", "kind": "function", "line": 1, "language": "python"}],
                "imports": [],
                "metadata_only": False,
                "provider": "tree_sitter",
                "reason": "",
                "size_bytes": 10,
            }
        )
    write_repomap_index(repo, {"version": 1, "provider": "tree_sitter", "mode": "full", "files": records})

    context = load_continuity_context(repo, request_text="startup banner")

    assert sum(1 for item in context["ranked_items"] if item["kind"] == "repo_map") == 3


def test_repomap_weak_items_do_not_displace_handoff_when_strong_map_item_exists(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    write_repomap_config(repo, {"enabled": True})
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "continuity.py").write_text("def render_startup_banner():\n    pass\n", encoding="utf-8")
    (repo / "docs").mkdir(parents=True)
    (repo / "docs" / "startup.md").write_text("# Startup Banner\n", encoding="utf-8")
    write_json(
        repo / HANDOFF_PATH,
        {
            "source_execution_id": "previous-task",
            "summary": "continue startup banner work",
            "recommended_starting_points": ["src/continuity.py"],
        },
    )
    write_repomap_index(
        repo,
        {
            "version": 1,
            "provider": "tree_sitter",
            "mode": "full",
            "files": [
                {
                    "path": "src/continuity.py",
                    "language": "python",
                    "symbols": [{"name": "render_startup_banner", "kind": "function", "line": 1, "language": "python"}],
                    "imports": [],
                    "metadata_only": False,
                    "provider": "tree_sitter",
                    "reason": "",
                    "size_bytes": 10,
                },
                {
                    "path": "docs/startup.md",
                    "language": "markdown",
                    "symbols": [{"name": "Startup Banner", "kind": "heading", "line": 1, "language": "markdown"}],
                    "imports": [],
                    "metadata_only": False,
                    "provider": "tree_sitter",
                    "reason": "",
                    "size_bytes": 10,
                },
            ],
        },
    )

    context = load_continuity_context(repo, request_text="startup banner")

    assert context["ranked_items"][0]["kind"] == "handoff"
    assert [item["paths"] for item in context["ranked_items"] if item["kind"] == "repo_map"] == [["src/continuity.py"]]


def test_repomap_active_weak_item_can_contribute_without_strong_symbol(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    write_repomap_config(repo, {"enabled": True})
    (repo / "docs").mkdir(parents=True)
    (repo / "docs" / "startup.md").write_text("# Startup Banner\n", encoding="utf-8")
    write_repomap_index(
        repo,
        {
            "version": 1,
            "provider": "tree_sitter",
            "mode": "full",
            "files": [
                {
                    "path": "docs/startup.md",
                    "language": "markdown",
                    "symbols": [{"name": "Startup Banner", "kind": "heading", "line": 1, "language": "markdown"}],
                    "imports": [],
                    "metadata_only": False,
                    "provider": "tree_sitter",
                    "reason": "",
                    "size_bytes": 10,
                }
            ],
        },
    )

    context = load_continuity_context(repo, request_text="startup banner", files=["docs/startup.md"])

    repo_map_items = [item for item in context["ranked_items"] if item["kind"] == "repo_map"]
    assert repo_map_items
    assert repo_map_items[0]["paths"] == ["docs/startup.md"]

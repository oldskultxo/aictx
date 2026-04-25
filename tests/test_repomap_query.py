from __future__ import annotations

from pathlib import Path

from aictx.repo_map.config import write_repomap_index
from aictx.repo_map.query import query_repo_map


def _write_index(repo: Path, files: list[dict]) -> None:
    write_repomap_index(
        repo,
        {
            "version": 1,
            "provider": "tree_sitter",
            "mode": "full",
            "discovery_source": "scan",
            "ignore_source": "none",
            "files": files,
        },
    )


def test_symbol_match_outranks_metadata_only_path_match(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "src").mkdir()
    (repo / "docs").mkdir()
    (repo / "src" / "continuity.py").write_text("def render_startup_banner():\n    pass\n", encoding="utf-8")
    (repo / "docs" / "startup_banner_notes.txt").write_text("notes\n", encoding="utf-8")
    _write_index(
        repo,
        [
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
                "path": "docs/startup_banner_notes.txt",
                "language": "",
                "symbols": [],
                "imports": [],
                "metadata_only": True,
                "provider": "tree_sitter",
                "reason": "unsupported_language",
                "size_bytes": 10,
            },
        ],
    )

    results = query_repo_map(repo, "startup banner")

    assert results[0]["path"] == "src/continuity.py"
    assert "repo_map:symbol_match" in results[0]["reasons"]
    assert results[0]["score"] > results[1]["score"]


def test_test_candidate_appears_for_matching_test_file(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "tests").mkdir()
    (repo / "tests" / "test_startup_banner.py").write_text("def test_banner():\n    pass\n", encoding="utf-8")
    _write_index(
        repo,
        [
            {
                "path": "tests/test_startup_banner.py",
                "language": "python",
                "symbols": [{"name": "test_banner", "kind": "function", "line": 1, "language": "python"}],
                "imports": [],
                "metadata_only": False,
                "provider": "tree_sitter",
                "reason": "",
                "size_bytes": 10,
            }
        ],
    )

    results = query_repo_map(repo, "startup banner")

    assert results
    assert results[0]["path"] == "tests/test_startup_banner.py"
    assert "repo_map:test_candidate" in results[0]["reasons"]


def test_no_index_returns_empty_list(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()

    assert query_repo_map(repo, "startup banner") == []


def test_results_are_sorted_deterministically(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "src").mkdir()
    (repo / "src" / "b_startup.py").write_text("def startup_banner():\n    pass\n", encoding="utf-8")
    (repo / "src" / "a_startup.py").write_text("def startup_banner():\n    pass\n", encoding="utf-8")
    _write_index(
        repo,
        [
            {
                "path": "src/b_startup.py",
                "language": "python",
                "symbols": [{"name": "startup_banner", "kind": "function", "line": 1, "language": "python"}],
                "imports": [],
                "metadata_only": False,
                "provider": "tree_sitter",
                "reason": "",
                "size_bytes": 10,
            },
            {
                "path": "src/a_startup.py",
                "language": "python",
                "symbols": [{"name": "startup_banner", "kind": "function", "line": 1, "language": "python"}],
                "imports": [],
                "metadata_only": False,
                "provider": "tree_sitter",
                "reason": "",
                "size_bytes": 10,
            },
        ],
    )

    results = query_repo_map(repo, "startup banner")

    assert [item["path"] for item in results] == ["src/a_startup.py", "src/b_startup.py"]


def test_strong_symbol_beats_heading_and_module_pseudosymbols(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "src").mkdir()
    (repo / "docs").mkdir()
    (repo / "src" / "runtime.py").write_text("def startup_banner():\n    pass\n", encoding="utf-8")
    (repo / "docs" / "runtime.md").write_text("# Startup Banner\n", encoding="utf-8")
    (repo / "src" / "startup.py").write_text("\"\"\"Startup module.\"\"\"\n", encoding="utf-8")
    _write_index(
        repo,
        [
            {
                "path": "docs/runtime.md",
                "language": "markdown",
                "symbols": [{"name": "Startup Banner", "kind": "heading", "line": 1, "language": "markdown"}],
                "metadata_only": False,
            },
            {
                "path": "src/startup.py",
                "language": "python",
                "symbols": [{"name": "startup", "kind": "module", "line": 1, "language": "python"}],
                "metadata_only": False,
            },
            {
                "path": "src/runtime.py",
                "language": "python",
                "symbols": [{"name": "startup_banner", "kind": "function", "line": 1, "language": "python"}],
                "metadata_only": False,
            },
        ],
    )

    results = query_repo_map(repo, "startup banner")

    assert results[0]["path"] == "src/runtime.py"
    assert results[0]["metadata"]["symbol_kind"] == "function"
    assert all(item["score"] < results[0]["score"] for item in results[1:])


def test_generic_query_does_not_promote_weak_pseudosymbols_without_context(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "src").mkdir()
    (repo / "src" / "__init__.py").write_text("", encoding="utf-8")
    (repo / "docs").mkdir()
    (repo / "docs" / "setup.md").write_text("# Setup\n", encoding="utf-8")
    _write_index(
        repo,
        [
            {
                "path": "src/__init__.py",
                "language": "python",
                "symbols": [{"name": "__init__", "kind": "module", "line": 1, "language": "python"}],
                "metadata_only": False,
            },
            {
                "path": "docs/setup.md",
                "language": "markdown",
                "symbols": [{"name": "Setup", "kind": "heading", "line": 1, "language": "markdown"}],
                "metadata_only": False,
            },
        ],
    )

    assert query_repo_map(repo, "init setup") == []


def test_active_file_context_can_boost_low_strength_match(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "docs").mkdir()
    (repo / "docs" / "setup.md").write_text("# Setup\n", encoding="utf-8")
    _write_index(
        repo,
        [
            {
                "path": "docs/setup.md",
                "language": "markdown",
                "symbols": [{"name": "Setup", "kind": "heading", "line": 1, "language": "markdown"}],
                "metadata_only": False,
            },
        ],
    )

    results = query_repo_map(repo, "setup", files=["docs/setup.md"])

    assert results
    assert results[0]["path"] == "docs/setup.md"
    assert "repo_map:live_path" in results[0]["reasons"]

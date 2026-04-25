from __future__ import annotations

import json
from pathlib import Path

import aictx.repo_map.refresh as refresh_module
from aictx.repo_map.config import load_repomap_status, write_repomap_config, write_repomap_index, write_repomap_manifest
from aictx.repo_map.index import build_repomap_index
from aictx.repo_map.manifest import build_repomap_manifest, file_manifest_entries
from aictx.repo_map.paths import repo_map_index_path


def _record(repo: Path, relative_path: str, symbol: str = "") -> dict:
    stat = (repo / relative_path).stat()
    return {
        "path": relative_path,
        "language": "python",
        "symbols": [{"name": symbol, "kind": "function", "line": 1, "end_line": 1, "language": "python"}] if symbol else [],
        "imports": [],
        "metadata_only": False,
        "provider": "tree_sitter",
        "reason": "",
        "size_bytes": int(stat.st_size),
        "mtime_ns": int(stat.st_mtime_ns),
    }


def _seed(repo: Path, paths: list[str]) -> None:
    records = [_record(repo, path, Path(path).stem) for path in paths]
    write_repomap_index(
        repo,
        build_repomap_index(records=records, discovery_source="scan", ignore_source="none", mode="full"),
    )
    write_repomap_manifest(
        repo,
        build_repomap_manifest(
            files_discovered=len(paths),
            files_indexed=len(records),
            symbols_indexed=sum(len(record["symbols"]) for record in records),
            discovery_source="scan",
            ignore_source="none",
            mode="full",
            file_entries=file_manifest_entries(repo, paths),
        ),
    )


def _patch_provider(monkeypatch):
    monkeypatch.setattr(refresh_module, "check_tree_sitter_available", lambda: {"available": True, "provider": "tree_sitter", "version": "x", "languages_count": 1, "error": ""})


def _patch_discovery(monkeypatch, paths: list[str]):
    monkeypatch.setattr(refresh_module, "discover_repo_files", lambda repo_root: {"files": sorted(paths), "discovery_source": "scan", "ignore_source": "none"})


def test_quick_refresh_unchanged_files_are_not_reparsed(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "one.py").write_text("def one(): pass\n", encoding="utf-8")
    write_repomap_config(repo, {"enabled": True})
    _seed(repo, ["one.py"])
    _patch_provider(monkeypatch)
    _patch_discovery(monkeypatch, ["one.py"])
    monkeypatch.setattr(refresh_module, "extract_file_structure", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("unchanged file reparsed")))

    payload = refresh_module.refresh_repo_map(repo, mode="quick")

    assert payload["status"] == "ok"
    assert payload["files_reparsed"] == 0
    assert load_repomap_status(repo)["files_reparsed"] == 0


def test_quick_refresh_changed_file_updates_only_that_file(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "one.py").write_text("def one(): pass\n", encoding="utf-8")
    (repo / "two.py").write_text("def two(): pass\n", encoding="utf-8")
    _seed(repo, ["one.py", "two.py"])
    (repo / "one.py").write_text("def one_changed(): pass\n", encoding="utf-8")
    _patch_provider(monkeypatch)
    _patch_discovery(monkeypatch, ["one.py", "two.py"])
    calls: list[str] = []

    def fake_extract(path: Path, repo_root: Path, max_parse_file_bytes: int) -> dict:
        calls.append(path.relative_to(repo_root).as_posix())
        return _record(repo_root, "one.py", "one_changed")

    monkeypatch.setattr(refresh_module, "extract_file_structure", fake_extract)

    payload = refresh_module.refresh_repo_map(repo, mode="quick")

    assert payload["status"] == "ok"
    assert calls == ["one.py"]
    index = json.loads(repo_map_index_path(repo).read_text(encoding="utf-8"))
    by_path = {record["path"]: record for record in index["files"]}
    assert by_path["one.py"]["symbols"][0]["name"] == "one_changed"
    assert by_path["two.py"]["symbols"][0]["name"] == "two"


def test_quick_refresh_deleted_file_removed_from_index(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "one.py").write_text("def one(): pass\n", encoding="utf-8")
    (repo / "two.py").write_text("def two(): pass\n", encoding="utf-8")
    _seed(repo, ["one.py", "two.py"])
    (repo / "two.py").unlink()
    _patch_provider(monkeypatch)
    _patch_discovery(monkeypatch, ["one.py"])

    payload = refresh_module.refresh_repo_map(repo, mode="quick")

    assert payload["status"] == "ok"
    index = json.loads(repo_map_index_path(repo).read_text(encoding="utf-8"))
    assert [record["path"] for record in index["files"]] == ["one.py"]


def test_quick_refresh_max_changed_files_cap_produces_partial(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "one.py").write_text("def one(): pass\n", encoding="utf-8")
    _seed(repo, ["one.py"])
    (repo / "two.py").write_text("def two(): pass\n", encoding="utf-8")
    (repo / "three.py").write_text("def three(): pass\n", encoding="utf-8")
    _patch_provider(monkeypatch)
    _patch_discovery(monkeypatch, ["one.py", "two.py", "three.py"])
    monkeypatch.setattr(refresh_module, "extract_file_structure", lambda path, repo_root, max_parse_file_bytes: _record(repo_root, path.relative_to(repo_root).as_posix()))

    payload = refresh_module.refresh_repo_map(repo, mode="quick", max_changed_files=1)

    assert payload["status"] == "partial"
    assert payload["files_reparsed"] == 1
    assert payload["files_pending"] == 1
    assert "max_changed_files_exceeded" in payload["warnings"]


def test_quick_refresh_budget_exceeded_preserves_existing_index(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "one.py").write_text("def one(): pass\n", encoding="utf-8")
    _seed(repo, ["one.py"])
    original = repo_map_index_path(repo).read_text(encoding="utf-8")
    (repo / "one.py").write_text("def one_changed(): pass\n", encoding="utf-8")
    _patch_provider(monkeypatch)
    _patch_discovery(monkeypatch, ["one.py"])
    monkeypatch.setattr(refresh_module, "extract_file_structure", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("budget should stop parse")))

    payload = refresh_module.refresh_repo_map(repo, mode="quick", budget_ms=0)

    assert payload["status"] == "partial"
    assert payload["files_reparsed"] == 0
    assert payload["files_pending"] == 1
    assert "budget_exceeded" in payload["warnings"]
    assert json.loads(repo_map_index_path(repo).read_text(encoding="utf-8"))["files"] == json.loads(original)["files"]


def test_quick_refresh_without_existing_index_needs_full_refresh(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "one.py").write_text("def one(): pass\n", encoding="utf-8")
    _patch_discovery(monkeypatch, ["one.py"])
    monkeypatch.setattr(refresh_module, "extract_file_structure", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("quick must not full parse missing index")))

    payload = refresh_module.refresh_repo_map(repo, mode="quick")

    assert payload["status"] == "needs_full_refresh"
    assert payload["files_reparsed"] == 0

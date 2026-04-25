from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from aictx.repo_map.discovery import discover_repo_files


@pytest.mark.skipif(shutil.which("git") is None, reason="git unavailable")
def test_git_discovery_respects_gitignore(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    (repo / ".gitignore").write_text("ignored.txt\n", encoding="utf-8")
    (repo / "tracked.py").write_text("print('x')\n", encoding="utf-8")
    (repo / "visible.txt").write_text("ok\n", encoding="utf-8")
    (repo / "ignored.txt").write_text("nope\n", encoding="utf-8")
    subprocess.run(["git", "add", ".gitignore", "tracked.py"], cwd=repo, check=True, capture_output=True)

    payload = discover_repo_files(repo)

    assert payload["discovery_source"] == "git"
    assert payload["ignore_source"] == "git"
    assert "tracked.py" in payload["files"]
    assert "visible.txt" in payload["files"]
    assert "ignored.txt" not in payload["files"]


def test_non_git_discovery_includes_files_and_marks_none(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "a.py").write_text("print('x')\n", encoding="utf-8")
    (repo / "sub").mkdir()
    (repo / "sub" / "b.txt").write_text("y\n", encoding="utf-8")

    payload = discover_repo_files(repo)

    assert payload["discovery_source"] == "scan"
    assert payload["ignore_source"] == "none"
    assert payload["files"] == ["a.py", "sub/b.txt"]

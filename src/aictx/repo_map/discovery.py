from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any


def discover_repo_files(repo_root: Path) -> dict[str, Any]:
    repo_root = Path(repo_root)
    git_result = _discover_git_files(repo_root)
    if git_result is not None:
        return git_result

    files = sorted(
        path.relative_to(repo_root).as_posix()
        for path in repo_root.rglob("*")
        if path.is_file()
    )
    return {
        "files": files,
        "discovery_source": "scan",
        "ignore_source": "none",
    }


def _discover_git_files(repo_root: Path) -> dict[str, Any] | None:
    try:
        probe = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    if probe.returncode != 0:
        return None

    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=repo_root,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    files = sorted(item for item in result.stdout.decode("utf-8", errors="replace").split("\x00") if item)
    return {
        "files": files,
        "discovery_source": "git",
        "ignore_source": "git",
    }

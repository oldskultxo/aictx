from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any


_GENERATED_PATH_PARTS = {
    ".aictx",
    ".aictx_cost",
    ".aictx_failure_memory",
    ".aictx_global_metrics",
    ".aictx_library",
    ".aictx_memory",
    ".aictx_memory_graph",
    ".aictx_task_memory",
    ".git",
    ".hg",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".svn",
    ".venv",
    ".venv-test",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
}


def discover_repo_files(repo_root: Path) -> dict[str, Any]:
    repo_root = Path(repo_root)
    git_result = _discover_git_files(repo_root)
    if git_result is not None:
        return git_result

    files = sorted(
        path.relative_to(repo_root).as_posix()
        for path in repo_root.rglob("*")
        if path.is_file() and _is_discoverable(path.relative_to(repo_root).as_posix())
    )
    return {
        "files": files,
        "discovery_source": "scan",
        "ignore_source": "aictx_defaults",
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
    files = sorted(
        item
        for item in result.stdout.decode("utf-8", errors="replace").split("\x00")
        if item and _is_discoverable(item)
    )
    return {
        "files": files,
        "discovery_source": "git",
        "ignore_source": "git+aictx_defaults",
    }


def _is_discoverable(relative_path: str) -> bool:
    parts = Path(str(relative_path or "").replace("\\", "/")).parts
    if not parts:
        return False
    return not any(part in _GENERATED_PATH_PARTS for part in parts)

from __future__ import annotations

import importlib.util
import subprocess
import sys
from typing import Any

REPO_MAP_PROVIDER = "tree_sitter"
REPO_MAP_IMPORT_NAME = "tree_sitter_language_pack"
REPO_MAP_PACKAGE_SPEC = "tree-sitter-language-pack>=1.6.0"


def repomap_dependency_available() -> bool:
    return importlib.util.find_spec(REPO_MAP_IMPORT_NAME) is not None


def install_repomap_dependency() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "pip", "install", REPO_MAP_PACKAGE_SPEC],
        capture_output=True,
        text=True,
        check=False,
    )


def update_global_repomap_config(config: dict[str, Any], *, requested: bool, available: bool) -> dict[str, Any]:
    updated = dict(config)
    if not requested:
        updated.pop("repomap", None)
        return updated
    updated["repomap"] = {
        "requested": True,
        "provider": REPO_MAP_PROVIDER,
        "available": bool(available),
    }
    return updated

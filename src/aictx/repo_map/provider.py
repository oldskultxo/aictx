from __future__ import annotations

from pathlib import Path
from typing import Any

from .tree_sitter_provider import check_tree_sitter_available, extract_file_structure


def check_provider_available(provider: str = "tree_sitter") -> dict[str, Any]:
    if provider != "tree_sitter":
        return {
            "available": False,
            "provider": provider,
            "version": "",
            "languages_count": 0,
            "error": "unsupported_provider",
        }
    return check_tree_sitter_available()


def extract_file_structure_for_provider(
    path: Path,
    repo_root: Path,
    max_parse_file_bytes: int,
    *,
    provider: str = "tree_sitter",
) -> dict[str, Any]:
    if provider != "tree_sitter":
        return {
            "path": Path(path).as_posix(),
            "language": "",
            "symbols": [],
            "imports": [],
            "metadata_only": True,
            "provider": provider,
            "reason": "unsupported_provider",
            "size_bytes": 0,
        }
    return extract_file_structure(path, repo_root, max_parse_file_bytes)


__all__ = [
    "check_tree_sitter_available",
    "check_provider_available",
    "extract_file_structure",
    "extract_file_structure_for_provider",
]

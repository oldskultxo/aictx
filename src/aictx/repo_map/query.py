from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .config import load_repomap_index

_TOKEN_RE = re.compile(r"[a-zA-Z0-9_]+")


def _tokenize(value: str) -> set[str]:
    raw = str(value or "").replace("_", " ")
    tokens = {token.lower() for token in _TOKEN_RE.findall(raw) if token}
    for token in list(tokens):
        if "_" in token:
            tokens.update(part.lower() for part in token.split("_") if part)
    return tokens


def _path_parts(path: str) -> tuple[str, str]:
    normalized = str(path or "").replace("\\", "/")
    file_name = normalized.rsplit("/", 1)[-1]
    return file_name, normalized.rsplit(".", 1)[0]


def query_repo_map(repo_root: Path, request_text: str, *, files: list[str] | None = None, limit: int = 8) -> list[dict[str, Any]]:
    repo_root = Path(repo_root)
    index_payload = load_repomap_index(repo_root)
    records = index_payload.get("files", []) if isinstance(index_payload, dict) else []
    if not isinstance(records, list):
        return []

    query_tokens = _tokenize(request_text)
    active_files = {str(path or "").strip().replace("\\", "/") for path in (files or []) if str(path or "").strip()}
    if not query_tokens:
        return []

    results: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        path = str(record.get("path") or "").strip().replace("\\", "/")
        if not path:
            continue
        live_path = (repo_root / path).exists()
        if not live_path:
            continue

        reasons: list[str] = []
        score = 0
        file_name, path_no_ext = _path_parts(path)
        path_tokens = _tokenize(path)
        file_tokens = _tokenize(file_name)

        symbol_hits: list[dict[str, Any]] = []
        raw_symbols = record.get("symbols", [])
        if isinstance(raw_symbols, list):
            for item in raw_symbols:
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name") or "").strip()
                if not name:
                    continue
                name_tokens = _tokenize(name)
                matches = query_tokens.intersection(name_tokens)
                if not matches:
                    continue
                symbol_hits.append(item)
                score += 50 + len(matches) * 8
            if symbol_hits:
                reasons.append("repo_map:symbol_match")

        path_matches = query_tokens.intersection(path_tokens)
        if path_matches:
            score += 18 + len(path_matches) * 5
            reasons.append("repo_map:path_match")

        scope_tokens = _tokenize(path_no_ext.replace("/", " "))
        scope_matches = query_tokens.intersection(scope_tokens)
        if scope_matches and "repo_map:path_match" not in reasons:
            score += 14 + len(scope_matches) * 3
            reasons.append("repo_map:scope_match")

        if record.get("metadata_only") and path_matches:
            score += 10
            reasons.append("repo_map:metadata_match")

        if path.startswith("tests/") or "/tests/" in f"/{path}":
            if query_tokens.intersection(file_tokens.union(scope_tokens)):
                score += 20
                reasons.append("repo_map:test_candidate")

        if file_name in {"main.py", "cli.py", "__init__.py"} or any(token in {"main", "cli", "entry", "init"} for token in query_tokens.intersection(file_tokens)):
            score += 8
            reasons.append("repo_map:entrypoint_candidate")

        if path in active_files:
            score += 16
            reasons.append("repo_map:live_path")
        elif live_path:
            score += 4
            reasons.append("repo_map:live_path")

        if score <= 0:
            continue

        symbol = symbol_hits[0] if symbol_hits else {}
        symbol_name = str(symbol.get("name") or file_name)
        item_id = f"{path}::{symbol_name}" if symbol_name and symbol_hits else path
        results.append(
            {
                "kind": "repo_map",
                "id": item_id,
                "title": symbol_name if symbol_name else path,
                "score": score,
                "reasons": reasons,
                "paths": [path],
                "metadata": {
                    "symbol": str(symbol.get("name") or ""),
                    "symbol_kind": str(symbol.get("kind") or ""),
                    "language": str(symbol.get("language") or record.get("language") or ""),
                    "line": int(symbol.get("line") or 0),
                },
                # compatibility fields for current CLI/task 5
                "path": path,
                "symbols": [str(item.get("name") or "") for item in symbol_hits if str(item.get("name") or "").strip()][:10],
            }
        )

    results.sort(key=lambda item: (-int(item.get("score", 0)), str(item.get("id", "")), str(item.get("path", ""))))
    return results[: max(1, int(limit))]

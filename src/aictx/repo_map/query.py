from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .config import load_repomap_index

_TOKEN_RE = re.compile(r"[a-zA-Z0-9_]+")


def _tokenize(value: str) -> set[str]:
    return {token.lower() for token in _TOKEN_RE.findall(value or "") if token}


def query_repo_map(repo_root: Path, query_text: str, *, limit: int = 10) -> list[dict[str, Any]]:
    index_payload = load_repomap_index(Path(repo_root))
    records = index_payload.get("files", []) if isinstance(index_payload, dict) else []
    if not isinstance(records, list):
        return []

    query_tokens = _tokenize(query_text)
    if not query_tokens:
        return []

    hits: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        path = str(record.get("path") or "")
        if not path:
            continue

        score = 0
        reasons: list[str] = []

        path_tokens = _tokenize(path)
        path_matches = query_tokens.intersection(path_tokens)
        if path_matches:
            score += len(path_matches) * 12
            reasons.append("repo_map:path_match")

        symbols: list[str] = []
        symbol_records = record.get("symbols", [])
        if isinstance(symbol_records, list):
            seen_symbols: set[str] = set()
            for item in symbol_records:
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name") or "").strip()
                if not name:
                    continue
                if query_tokens.intersection(_tokenize(name)):
                    if name not in seen_symbols:
                        symbols.append(name)
                        seen_symbols.add(name)
            if symbols:
                score += 40 + len(symbols) * 8
                reasons.append("repo_map:symbol_match")

        if score <= 0:
            continue

        hits.append(
            {
                "path": path,
                "score": score,
                "reasons": reasons,
                "symbols": symbols[:10],
            }
        )

    hits.sort(key=lambda item: (-int(item.get("score", 0)), str(item.get("path", ""))))
    return hits[: max(1, int(limit))]

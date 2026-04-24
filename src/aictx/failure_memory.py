from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .runtime_io import slugify
from .state import REPO_FAILURE_MEMORY_DIR, read_json, read_jsonl, write_json

FAILURE_PATTERNS_PATH = REPO_FAILURE_MEMORY_DIR / "failure_patterns.jsonl"
FAILURE_INDEX_PATH = REPO_FAILURE_MEMORY_DIR / "failure_index.json"


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def failure_signature(task_type: str, errors: list[str], command: str = "") -> str:
    basis = " ".join(errors[:2] or [command, task_type]).strip() or "unknown_failure"
    return slugify(f"{task_type}:{basis}")[:96]


def load_failures(repo_root: Path) -> list[dict[str, Any]]:
    return read_jsonl(repo_root / FAILURE_PATTERNS_PATH)


def write_failure_index(repo_root: Path, rows: list[dict[str, Any]]) -> None:
    index = {
        "version": 1,
        "failure_count": len(rows),
        "records": [
            {
                "failure_id": row.get("failure_id"),
                "signature": row.get("signature"),
                "task_type": row.get("task_type"),
                "status": row.get("status"),
                "area_id": row.get("area_id"),
            }
            for row in rows
        ],
    }
    write_json(repo_root / FAILURE_INDEX_PATH, index)


def persist_failure_pattern(repo_root: Path, prepared: dict[str, Any], execution_log: dict[str, Any], result: dict[str, Any]) -> dict[str, Any] | None:
    errors = list(execution_log.get("notable_errors", [])) if isinstance(execution_log.get("notable_errors"), list) else []
    commands = list(execution_log.get("commands_executed", [])) if isinstance(execution_log.get("commands_executed"), list) else []
    if not errors and result.get("success"):
        return None
    signature = failure_signature(str(execution_log.get("task_type") or "unknown"), errors, commands[0] if commands else "")
    rows = load_failures(repo_root)
    existing = next((row for row in rows if row.get("signature") == signature and row.get("status") != "resolved"), None)
    record = {
        "failure_id": existing.get("failure_id") if existing else f"failure::{signature}",
        "signature": signature,
        "task_type": str(execution_log.get("task_type") or "unknown"),
        "area_id": str(execution_log.get("area_id") or "unknown"),
        "error_text": "\n".join(errors[:3]),
        "failed_command": commands[0] if commands else "",
        "files_involved": list(execution_log.get("files_opened", [])) if isinstance(execution_log.get("files_opened"), list) else [],
        "attempted_fix_summary": str(result.get("result_summary") or ""),
        "status": "open",
        "resolved_by_execution_id": "",
        "occurrences": int(existing.get("occurrences", 0) or 0) + 1 if existing else 1,
        "last_execution_id": str(prepared.get("envelope", {}).get("execution_id") or ""),
    }
    append_jsonl(repo_root / FAILURE_PATTERNS_PATH, record)
    write_failure_index(repo_root, load_failures(repo_root))
    return {"path": (repo_root / FAILURE_PATTERNS_PATH).as_posix(), "failure_id": record["failure_id"], "signature": signature}


def lookup_failures(repo_root: Path, *, task_type: str = "", text: str = "", files: list[str] | None = None, area_id: str = "") -> list[dict[str, Any]]:
    rows = [row for row in load_failures(repo_root) if row.get("status") != "resolved"]
    tokens = {token for token in slugify(text).split("_") if len(token) > 2}
    file_set = set(files or [])
    ranked: list[tuple[int, dict[str, Any]]] = []
    for row in rows:
        score = 0
        if task_type and row.get("task_type") == task_type:
            score += 5
        if area_id and row.get("area_id") == area_id:
            score += 4
        if file_set.intersection(set(row.get("files_involved", []))):
            score += 3
        haystack = slugify(" ".join([str(row.get("error_text", "")), str(row.get("failed_command", "")), str(row.get("attempted_fix_summary", ""))]))
        score += len(tokens.intersection(set(haystack.split("_"))))
        if score:
            ranked.append((score, row))
    ranked.sort(key=lambda item: (-item[0], str(item[1].get("failure_id", ""))))
    return [{**row, "match_score": score} for score, row in ranked[:3]]


def link_resolved_failures(repo_root: Path, prepared: dict[str, Any], execution_log: dict[str, Any]) -> list[str]:
    related = lookup_failures(
        repo_root,
        task_type=str(execution_log.get("task_type") or ""),
        text=str(prepared.get("envelope", {}).get("user_request") or ""),
        files=list(execution_log.get("files_opened", [])) if isinstance(execution_log.get("files_opened"), list) else [],
        area_id=str(execution_log.get("area_id") or ""),
    )
    if not related:
        return []
    rows = load_failures(repo_root)
    resolved_ids = {row["failure_id"] for row in related[:2]}
    updated: list[dict[str, Any]] = []
    for row in rows:
        if row.get("failure_id") in resolved_ids and row.get("status") != "resolved":
            row = dict(row)
            row["status"] = "resolved"
            row["resolved_by_execution_id"] = str(prepared.get("envelope", {}).get("execution_id") or "")
        updated.append(row)
    path = repo_root / FAILURE_PATTERNS_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in updated) + ("\n" if updated else ""), encoding="utf-8")
    write_failure_index(repo_root, updated)
    return sorted(resolved_ids)


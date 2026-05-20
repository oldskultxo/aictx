from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..continuity import DECISIONS_PATH, HANDOFF_PATH, HANDOFFS_HISTORY_PATH, RESUME_CAPSULE_JSON_PATH
from ..continuity_view import CONTINUITY_MAP_PATH
from ..doctor import build_doctor_report
from ..failures import FAILURE_PATTERNS_PATH
from ..state import read_json, read_jsonl
from ..work_state import list_work_states, load_active_work_state
from .tools import resolve_repo

RESOURCE_URIS = [
    "aictx://repo/current/resume-capsule",
    "aictx://repo/current/continuity-view",
    "aictx://repo/current/continuity-map",
    "aictx://repo/current/work-state",
    "aictx://repo/current/failure-memory",
    "aictx://repo/current/decisions",
    "aictx://repo/current/handoffs",
    "aictx://repo/current/repomap-status",
    "aictx://repo/current/doctor",
]


def list_resources() -> list[dict[str, str]]:
    return [{"uri": uri, "name": uri.rsplit("/", 1)[-1], "mimeType": "application/json"} for uri in RESOURCE_URIS]


def _compact_file(path: Path, *, max_chars: int = 12000) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False, "path": path.as_posix()}
    text = path.read_text(encoding="utf-8", errors="replace")
    return {"exists": True, "path": path.as_posix(), "truncated": len(text) > max_chars, "content": text[:max_chars]}


def read_resource(uri: str, repo_arg: str = ".") -> dict[str, Any]:
    repo = resolve_repo(repo_arg)
    if uri == "aictx://repo/current/resume-capsule":
        return {"uri": uri, "data": read_json(repo / RESUME_CAPSULE_JSON_PATH, {})}
    if uri == "aictx://repo/current/continuity-view":
        return {"uri": uri, "data": _compact_file(repo / ".aictx" / "reports" / "continuity-view.md")}
    if uri == "aictx://repo/current/continuity-map":
        return {"uri": uri, "data": _compact_file(repo / CONTINUITY_MAP_PATH)}
    if uri == "aictx://repo/current/work-state":
        return {"uri": uri, "data": {"active": load_active_work_state(repo), "tasks": list_work_states(repo)}}
    if uri == "aictx://repo/current/failure-memory":
        return {"uri": uri, "data": {"records": read_jsonl(repo / FAILURE_PATTERNS_PATH)[-25:]}}
    if uri == "aictx://repo/current/decisions":
        return {"uri": uri, "data": {"records": read_jsonl(repo / DECISIONS_PATH)[-25:]}}
    if uri == "aictx://repo/current/handoffs":
        return {"uri": uri, "data": {"current": read_json(repo / HANDOFF_PATH, {}), "history": read_jsonl(repo / HANDOFFS_HISTORY_PATH)[-25:]}}
    if uri == "aictx://repo/current/repomap-status":
        from ..cli import _repomap_status_payload
        return {"uri": uri, "data": _repomap_status_payload(repo)}
    if uri == "aictx://repo/current/doctor":
        return {"uri": uri, "data": build_doctor_report(repo)}
    raise KeyError(uri)


def resource_content(uri: str, repo: str = ".") -> dict[str, Any]:
    payload = read_resource(uri, repo)
    return {"contents": [{"uri": uri, "mimeType": "application/json", "text": json.dumps(payload["data"], ensure_ascii=False)}]}

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..adapters import infer_adapter_id, infer_agent_id
from ..area_memory import derive_area_id
from ..continuity import DECISIONS_PATH, HANDOFF_PATH, HANDOFFS_HISTORY_PATH, append_handoff_history, build_resume_capsule, load_continuity_context
from ..continuity.quality import build_continuity_quality_report
from ..continuity_view import write_continuity_view
from ..doctor import build_doctor_report
from ..failures import FAILURE_PATTERNS_PATH, failure_signature, load_failures, write_failure_index
from ..integrations.mcp_config import DEFAULT_MCP_PROFILE, install_repo_mcp_config, mcp_status, normalize_mcp_profile
from ..lifecycle import append_lifecycle_event, build_lifecycle_status
from ..messages import MESSAGE_MODE_MUTED, MESSAGE_MODE_UNMUTED, get_message_mode, set_message_mode
from ..middleware import finalize_execution, now_iso, prepare_execution
from ..portability import append_portable_jsonl, compact_portable_jsonl, portability_status, write_portable_json
from ..repo_map.query import query_repo_map
from ..repo_map.refresh import refresh_repo_map
from ..runtime_tasks import resolve_task_type
from ..state import read_json, read_jsonl, write_json
from ..strategy_memory import select_strategy
from ..task_context import build_task_context_pack
from ..work_state import changed_work_state_fields, close_work_state, list_work_states, load_active_work_state, load_work_state, start_work_state, update_work_state
from .permissions import FULL_TOOLS

MAX_TEXT_CHARS = 12000
MAX_LIST_ITEMS = 200
MAX_PATH_CHARS = 1000
SECRET_RE = re.compile(r"(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*[^\s,;]+")



def _schema(properties: dict[str, Any], *, required: list[str] | None = None, additional: bool = False) -> dict[str, Any]:
    payload: dict[str, Any] = {"type": "object", "properties": properties, "additionalProperties": additional}
    if required:
        payload["required"] = required
    return payload


_TEXT_PROP = {"type": "string"}
_STRING_LIST_PROP = {"type": "array", "items": {"type": "string"}, "maxItems": MAX_LIST_ITEMS}
_REPO_PROP = {"repo": _TEXT_PROP}
_OBSERVED_PROPS = {
    "files_opened": _STRING_LIST_PROP,
    "files_edited": _STRING_LIST_PROP,
    "commands_executed": _STRING_LIST_PROP,
    "tests_executed": _STRING_LIST_PROP,
    "notable_errors": _STRING_LIST_PROP,
}
_ADAPTER_PROP = {"adapter_id": _TEXT_PROP}
TOOL_INPUT_SCHEMAS: dict[str, dict[str, Any]] = {
    "aictx_resume": _schema({**_REPO_PROP, "task": _TEXT_PROP, "task_type": _TEXT_PROP, "mode": {"type": "string", "enum": ["brief", "standard", "full"]}, "agent_id": _TEXT_PROP, **_ADAPTER_PROP, "session_id": _TEXT_PROP}),
    "aictx_prepare_task_context": _schema({**_REPO_PROP, "goal": _TEXT_PROP, "task_type": _TEXT_PROP}, required=["goal"]),
    "aictx_lifecycle_status": _schema({**_REPO_PROP, "task": _TEXT_PROP, "session_id": _TEXT_PROP}),
    "aictx_finalize": _schema({**_REPO_PROP, "status": {"type": "string", "enum": ["success", "failure"]}, "summary": _TEXT_PROP, "task": _TEXT_PROP, "task_type": _TEXT_PROP, "agent_id": _TEXT_PROP, **_ADAPTER_PROP, "session_id": _TEXT_PROP, "include_view": {"type": "boolean"}, **_OBSERVED_PROPS}, required=["status", "summary"]),
    "aictx_task_start": _schema({**_REPO_PROP, "goal": _TEXT_PROP, "task_type": _TEXT_PROP, "hypothesis": _TEXT_PROP, "next_action": _TEXT_PROP, "files": _STRING_LIST_PROP, "risks": _STRING_LIST_PROP}, required=["goal"]),
    "aictx_task_update": _schema({**_REPO_PROP, "task_id": _TEXT_PROP, "goal": _TEXT_PROP, "status": _TEXT_PROP, "hypothesis": _TEXT_PROP, "next_action": _TEXT_PROP, "files": _STRING_LIST_PROP, "risks": _STRING_LIST_PROP, "verification": _TEXT_PROP}),
    "aictx_task_close": _schema({**_REPO_PROP, "task_id": _TEXT_PROP, "status": _TEXT_PROP, "summary": _TEXT_PROP, "next_action": _TEXT_PROP}),
    "aictx_map_query": _schema({**_REPO_PROP, "query": _TEXT_PROP, "limit": {"type": "integer", "minimum": 1, "maximum": 50}}, required=["query"]),
    "aictx_continuity_view_generate": _schema({**_REPO_PROP, "output": _TEXT_PROP}),
    "aictx_continuity_quality": _schema({**_REPO_PROP, "task": _TEXT_PROP, "task_type": _TEXT_PROP}),
    "aictx_doctor": _schema({**_REPO_PROP, "release_readiness": {"type": "boolean"}}),
    "aictx_messages_set": _schema({**_REPO_PROP, "mode": {"type": "string", "enum": [MESSAGE_MODE_MUTED, MESSAGE_MODE_UNMUTED]}}, required=["mode"]),
}

TOOL_DESCRIPTIONS = {
    "aictx_resume": "Build a resume capsule.",
    "aictx_prepare_task_context": "Compile a read-only task-specific context pack.",
    "aictx_lifecycle_status": "Inspect AICTX lifecycle status.",
    "aictx_next": "Return next-step guidance.",
    "aictx_view": "Inspect Continuity View metadata.",
    "aictx_continuity_view_generate": "Generate Continuity View files.",
    "aictx_continuity_quality": "Inspect continuity quality and freshness.",
    "aictx_doctor": "Run AICTX diagnostics.",
    "aictx_task_list": "List Work State tasks.",
    "aictx_task_show": "Show a Work State task.",
    "aictx_task_start": "Start Work State.",
    "aictx_task_update": "Update Work State.",
    "aictx_task_close": "Close Work State.",
    "aictx_finalize": "Finalize agent work.",
    "aictx_record_decision": "Record a decision.",
    "aictx_record_handoff": "Record a handoff.",
    "aictx_record_failure": "Record a failure pattern.",
    "aictx_strategy_suggest": "Suggest reusable strategy.",
    "aictx_map_status": "Show RepoMap status.",
    "aictx_map_query": "Query RepoMap.",
    "aictx_map_refresh": "Refresh RepoMap.",
    "aictx_portability_status": "Show portability status.",
    "aictx_portability_compact": "Compact portable JSONL.",
    "aictx_messages_status": "Show message mode.",
    "aictx_messages_set": "Set message mode.",
    "aictx_report_real_usage": "Build real usage report.",
}


def ok(**payload: Any) -> dict[str, Any]:
    return {"ok": True, **payload}


def error(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"ok": False, "error": {"code": code, "message": message, "details": details or {}}}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def scrub_text(value: str) -> str:
    return SECRET_RE.sub(lambda m: f"{m.group(1)}=<redacted>", value)


def _text(value: Any, name: str, *, required: bool = False, max_chars: int = MAX_TEXT_CHARS) -> str:
    text = scrub_text(str(value or "").strip())
    if required and not text:
        raise ValueError(f"{name} is required")
    if len(text) > max_chars:
        raise ValueError(f"{name} exceeds {max_chars} chars")
    return text


def _list(value: Any, name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{name} must be a list")
    if len(value) > MAX_LIST_ITEMS:
        raise ValueError(f"{name} exceeds {MAX_LIST_ITEMS} items")
    result: list[str] = []
    for item in value:
        text = _text(item, name, max_chars=MAX_PATH_CHARS)
        if text:
            result.append(text)
    return result


def resolve_repo(repo: str | Path | None = None) -> Path:
    root = Path(str(repo or ".")).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise ValueError(f"repo does not exist or is not a directory: {repo or '.'}")
    return root


def _task_type(request: str, explicit: str = "", files: list[str] | None = None) -> str:
    resolved = resolve_task_type(request, explicit_task_type=explicit or None, touched_files=files or [])
    return str(resolved.get("task_type") or explicit or "")


def tool_specs(names: set[str] | None = None) -> list[dict[str, Any]]:
    selected = names or FULL_TOOLS
    specs = []
    for name in sorted(selected):
        specs.append({
            "name": name,
            "description": TOOL_DESCRIPTIONS.get(name, name),
            "inputSchema": TOOL_INPUT_SCHEMAS.get(name, {"type": "object", "additionalProperties": True}),
        })
    return specs


def aictx_resume(args: dict[str, Any]) -> dict[str, Any]:
    repo = resolve_repo(args.get("repo"))
    task = _text(args.get("task"), "task")
    mode = str(args.get("mode") or "standard").lower()
    if mode not in {"brief", "standard", "full"}:
        return error("invalid_mode", "mode must be brief, standard or full")
    task_type = _task_type(task, _text(args.get("task_type"), "task_type"))
    agent_id = infer_agent_id(_text(args.get("agent_id"), "agent_id"), mcp_default=True)
    adapter_id = infer_adapter_id(_text(args.get("adapter_id"), "adapter_id"), agent_id=agent_id)
    session_id = _text(args.get("session_id"), "session_id")
    payload = build_resume_capsule(repo, request_text=task, full=(mode == "full"), task_type=task_type, agent_id=agent_id, adapter_id=adapter_id, session_id=session_id)
    contract_ref = payload.get("contract_ref") if isinstance(payload.get("contract_ref"), dict) else {}
    append_lifecycle_event(repo, {"event_type": "resume_called", "source": "mcp", "agent_id": agent_id, "adapter_id": adapter_id, "session_id": session_id, "task": task, "task_type": task_type, "contract_id": str(contract_ref.get("contract_id") or "")})
    contract = payload.get("execution_contract", {}) if isinstance(payload.get("execution_contract"), dict) else {}
    capsule = payload.get("capsule", {}) if isinstance(payload.get("capsule"), dict) else {}
    return ok(mode=mode, active_task=payload.get("active_task") or {}, next_action=str(capsule.get("next_action") or ""), known_failures=payload.get("failures", []), relevant_files=list(capsule.get("entry_points", []) or []), validation=contract.get("test_command", {}), continuity_brief=payload if mode != "brief" else capsule, suggested_followups=list(capsule.get("fallback_entry_points", []) or []))


def aictx_prepare_task_context(args: dict[str, Any]) -> dict[str, Any]:
    repo = resolve_repo(args.get("repo"))
    goal = _text(args.get("goal"), "goal", required=True)
    task_type = _text(args.get("task_type"), "task_type")
    return ok(task_context_pack=build_task_context_pack(repo, goal, task_type=task_type))


def aictx_lifecycle_status(args: dict[str, Any]) -> dict[str, Any]:
    repo = resolve_repo(args.get("repo"))
    return ok(lifecycle_status=build_lifecycle_status(repo, request_text=_text(args.get("task"), "task"), session_id=_text(args.get("session_id"), "session_id")))


def aictx_next(args: dict[str, Any]) -> dict[str, Any]:
    repo = resolve_repo(args.get("repo"))
    request = _text(args.get("request"), "request")
    files = _list(args.get("files_opened"), "files_opened")
    commands = _list(args.get("commands_executed"), "commands_executed")
    tests = _list(args.get("tests_executed"), "tests_executed")
    errors = _list(args.get("notable_errors"), "notable_errors")
    task_type = _task_type(request, _text(args.get("task_type"), "task_type"), files)
    context = load_continuity_context(repo, task_type=task_type, request_text=request, files=files, commands=commands, tests=tests, errors=errors, area_id=derive_area_id(files + tests) if files or tests else "")
    return ok(continuity_brief=context.get("continuity_brief", {}), ranked_items=context.get("ranked_items", []), why_loaded=context.get("why_loaded", {}))


def aictx_view(args: dict[str, Any]) -> dict[str, Any]:
    repo = resolve_repo(args.get("repo"))
    view_path = repo / ".aictx" / "reports" / "continuity-view.md"
    map_path = repo / ".aictx" / "reports" / "continuity-map.mmd"
    data = {"exists": view_path.exists() or map_path.exists(), "markdown_path": view_path.as_posix(), "mermaid_path": map_path.as_posix()}
    if bool(args.get("include_markdown")) and view_path.exists():
        data["markdown"] = view_path.read_text(encoding="utf-8")[:MAX_TEXT_CHARS]
    if bool(args.get("include_mermaid")) and map_path.exists():
        data["mermaid"] = map_path.read_text(encoding="utf-8")[:MAX_TEXT_CHARS]
    return ok(view=data)


def aictx_continuity_view_generate(args: dict[str, Any]) -> dict[str, Any]:
    repo = resolve_repo(args.get("repo"))
    out = _text(args.get("output"), "output", max_chars=MAX_PATH_CHARS)
    if out:
        target = (repo / out).resolve() if not Path(out).expanduser().is_absolute() else Path(out).expanduser().resolve()
        try:
            target.relative_to(repo)
        except ValueError:
            return error("invalid_output", "output must stay inside repo")
    payload = write_continuity_view(repo, output=out or None)
    return ok(changed=True, warnings=[], view=payload.get("view", {}))


def aictx_doctor(args: dict[str, Any]) -> dict[str, Any]:
    return ok(report=build_doctor_report(resolve_repo(args.get("repo")), release_readiness=bool(args.get("release_readiness"))))


def aictx_continuity_quality(args: dict[str, Any]) -> dict[str, Any]:
    repo = resolve_repo(args.get("repo"))
    task = _text(args.get("task"), "task")
    task_type = _task_type(task, _text(args.get("task_type"), "task_type")) if task else _text(args.get("task_type"), "task_type")
    return ok(continuity_quality=build_continuity_quality_report(repo, request_text=task, task_type=task_type))


def aictx_task_list(args: dict[str, Any]) -> dict[str, Any]:
    repo = resolve_repo(args.get("repo"))
    active = str(load_active_work_state(repo).get("task_id") or "")
    return ok(tasks=[{**state, "active": str(state.get("task_id") or "") == active} for state in list_work_states(repo)])


def aictx_task_show(args: dict[str, Any]) -> dict[str, Any]:
    state = load_work_state(resolve_repo(args.get("repo")), _text(args.get("task_id"), "task_id", required=True))
    return ok(found=bool(state), task=state)


def aictx_task_start(args: dict[str, Any]) -> dict[str, Any]:
    repo = resolve_repo(args.get("repo"))
    initial = {k: v for k, v in {"task_type": _text(args.get("task_type"), "task_type"), "hypothesis": _text(args.get("hypothesis"), "hypothesis"), "next_action": _text(args.get("next_action"), "next_action"), "files": _list(args.get("files"), "files"), "risks": _list(args.get("risks"), "risks")}.items() if v}
    state = start_work_state(repo, _text(args.get("goal"), "goal", required=True), initial=initial)
    append_lifecycle_event(repo, {"event_type": "work_state_started", "source": "mcp", "task": state.get("goal"), "task_type": initial.get("task_type", ""), "work_state_task_id": state.get("task_id"), "status": state.get("status")})
    return ok(changed=True, warnings=[], task=state)


def aictx_task_update(args: dict[str, Any]) -> dict[str, Any]:
    repo = resolve_repo(args.get("repo"))
    patch = {k: v for k, v in {"goal": _text(args.get("goal"), "goal"), "status": _text(args.get("status"), "status"), "hypothesis": _text(args.get("hypothesis"), "hypothesis"), "next_action": _text(args.get("next_action"), "next_action"), "files": _list(args.get("files"), "files"), "risks": _list(args.get("risks"), "risks"), "verification": _text(args.get("verification"), "verification")}.items() if v}
    before = load_work_state(repo, _text(args.get("task_id"), "task_id")) if args.get("task_id") else load_active_work_state(repo)
    state = update_work_state(repo, patch, task_id=_text(args.get("task_id"), "task_id") or None)
    changed = changed_work_state_fields(before, state, patch)
    append_lifecycle_event(repo, {"event_type": "work_state_updated", "source": "mcp", "task": state.get("goal"), "work_state_task_id": state.get("task_id"), "status": state.get("status")})
    return ok(changed=bool(changed), warnings=[], changed_fields=changed, task=state)


def aictx_task_close(args: dict[str, Any]) -> dict[str, Any]:
    repo = resolve_repo(args.get("repo"))
    status = _text(args.get("status") or "resolved", "status")
    patch = {k: v for k, v in {"summary": _text(args.get("summary"), "summary"), "next_action": _text(args.get("next_action"), "next_action")}.items() if v}
    state = close_work_state(repo, task_id=_text(args.get("task_id"), "task_id") or None, status=status, patch=patch)
    append_lifecycle_event(repo, {"event_type": "work_state_closed", "source": "mcp", "task": state.get("goal"), "work_state_task_id": state.get("task_id"), "status": state.get("status")})
    return ok(changed=True, warnings=[], task=state)


def aictx_finalize(args: dict[str, Any]) -> dict[str, Any]:
    repo = resolve_repo(args.get("repo"))
    status = _text(args.get("status"), "status", required=True)
    if status not in {"success", "failure"}:
        return error("invalid_status", "status must be success or failure")
    summary = _text(args.get("summary"), "summary", required=True)
    task = _text(args.get("task"), "task") or summary
    agent_id = infer_agent_id(_text(args.get("agent_id"), "agent_id"), mcp_default=True)
    adapter_id = infer_adapter_id(_text(args.get("adapter_id"), "adapter_id"), agent_id=agent_id)
    session_id = _text(args.get("session_id"), "session_id")
    execution_id = session_id or f"mcp-finalize-{now_iso()}"
    files_opened = _list(args.get("files_opened"), "files_opened")
    files_edited = _list(args.get("files_edited"), "files_edited")
    commands_executed = _list(args.get("commands_executed"), "commands_executed")
    tests_executed = _list(args.get("tests_executed"), "tests_executed")
    prepared = prepare_execution({"repo_root": repo.as_posix(), "user_request": task, "agent_id": agent_id, "adapter_id": adapter_id, "execution_id": execution_id, "timestamp": now_iso(), "declared_task_type": _text(args.get("task_type"), "task_type") or None, "execution_mode": "mcp", "files_opened": files_opened, "files_edited": files_edited, "commands_executed": commands_executed, "tests_executed": tests_executed, "notable_errors": _list(args.get("notable_errors"), "notable_errors"), "error_events": [], "work_state": {}, "skill_metadata": {}})
    payload = finalize_execution(prepared, {"success": status == "success", "result_summary": summary, "validated_learning": False, "decisions": [], "semantic_repo": [], "work_state": {}})
    append_lifecycle_event(repo, {"event_type": "finalize_called", "source": "mcp", "agent_id": agent_id, "adapter_id": adapter_id, "session_id": session_id, "execution_id": execution_id, "task": task, "task_type": _text(args.get("task_type"), "task_type"), "status": status, "files_opened_count": len(files_opened), "files_edited_count": len(files_edited), "commands_count": len(commands_executed), "tests_count": len(tests_executed)})
    if bool(args.get("include_view")):
        payload["continuity_view"] = write_continuity_view(repo).get("view", {})
    return ok(changed=True, warnings=[], summary=payload.get("agent_summary_text", ""), finalize=payload)


def aictx_record_decision(args: dict[str, Any]) -> dict[str, Any]:
    repo = resolve_repo(args.get("repo"))
    row = {"title": _text(args.get("title"), "title", required=True), "decision": _text(args.get("decision"), "decision", required=True), "rationale": _text(args.get("rationale"), "rationale"), "subsystem": _text(args.get("scope"), "scope"), "related_paths": _list(args.get("files"), "files"), "timestamp": utc_now(), "execution_id": "mcp-record-decision"}
    append_portable_jsonl(repo, repo / DECISIONS_PATH, row)
    return ok(changed=True, warnings=[], decision=row, path=(repo / DECISIONS_PATH).as_posix())


def aictx_record_handoff(args: dict[str, Any]) -> dict[str, Any]:
    repo = resolve_repo(args.get("repo"))
    handoff = {"summary": _text(args.get("summary"), "summary", required=True), "completed": [_text(args.get("summary"), "summary")], "next_steps": [_text(args.get("next_action"), "next_action")] if _text(args.get("next_action"), "next_action") else [], "blocked": [_text(args.get("blocked_on"), "blocked_on")] if _text(args.get("blocked_on"), "blocked_on") else [], "open_items": [], "risks": _list(args.get("risks"), "risks"), "recommended_starting_points": _list(args.get("files"), "files"), "updated_at": utc_now(), "source_execution_id": "mcp-record-handoff"}
    handoff["open_items"] = handoff["blocked"]
    write_json(repo / HANDOFF_PATH, handoff)
    append_handoff_history(repo, {"execution_id": "mcp-record-handoff", "timestamp": handoff["updated_at"], "summary": handoff["summary"], "next_steps": handoff["next_steps"], "blocked": handoff["blocked"], "risks": handoff["risks"], "status": "unresolved", "recommended_starting_points": handoff["recommended_starting_points"]})
    return ok(changed=True, warnings=[], handoff=handoff, path=(repo / HANDOFF_PATH).as_posix())


def aictx_record_failure(args: dict[str, Any]) -> dict[str, Any]:
    repo = resolve_repo(args.get("repo"))
    error_text = _text(args.get("error"), "error", required=True)
    command = _text(args.get("command"), "command")
    task_type = _text(args.get("task_type"), "task_type") or "unknown"
    signature = failure_signature(task_type, [error_text], command)
    row = {"failure_id": f"failure::{signature}", "signature": signature, "failure_signature": signature, "task_type": task_type, "error_text": error_text, "failed_command": command, "files_involved": _list(args.get("files"), "files"), "attempted_fix_summary": _text(args.get("resolution"), "resolution"), "resolution_hint": _text(args.get("resolution"), "resolution"), "status": "resolved" if args.get("resolution") else "open", "occurrences": 1, "timestamp": utc_now(), "last_execution_id": "mcp-record-failure"}
    append_portable_jsonl(repo, repo / FAILURE_PATTERNS_PATH, row)
    write_failure_index(repo, load_failures(repo))
    return ok(changed=True, warnings=[], failure=row, path=(repo / FAILURE_PATTERNS_PATH).as_posix())


def aictx_strategy_suggest(args: dict[str, Any]) -> dict[str, Any]:
    repo = resolve_repo(args.get("repo"))
    request = _text(args.get("request"), "request")
    files = _list(args.get("files_opened"), "files_opened")
    task_type = _task_type(request, _text(args.get("task_type"), "task_type"), files)
    strategy = select_strategy(repo, task_type, files=files, request_text=request, commands=_list(args.get("commands_executed"), "commands_executed"), tests=_list(args.get("tests_executed"), "tests_executed"), errors=_list(args.get("notable_errors"), "notable_errors"))
    return ok(strategy=strategy or {})


def aictx_map_status(args: dict[str, Any]) -> dict[str, Any]:
    from ..cli import _repomap_status_payload
    return ok(status=_repomap_status_payload(resolve_repo(args.get("repo"))))


def aictx_map_query(args: dict[str, Any]) -> dict[str, Any]:
    repo = resolve_repo(args.get("repo"))
    limit = int(args.get("limit") or 10)
    return ok(results=query_repo_map(repo, _text(args.get("query"), "query", required=True), limit=max(1, min(limit, 50))))


def aictx_map_refresh(args: dict[str, Any]) -> dict[str, Any]:
    repo = resolve_repo(args.get("repo"))
    mode = str(args.get("mode") or "incremental")
    if mode not in {"incremental", "full"}:
        return error("invalid_mode", "mode must be incremental or full")
    payload = refresh_repo_map(repo, mode=mode)
    return ok(changed=True, warnings=list(payload.get("warnings", []) if isinstance(payload.get("warnings"), list) else []), refresh=payload)


def aictx_portability_status(args: dict[str, Any]) -> dict[str, Any]:
    return ok(status=portability_status(resolve_repo(args.get("repo"))))


def aictx_portability_compact(args: dict[str, Any]) -> dict[str, Any]:
    payload = compact_portable_jsonl(resolve_repo(args.get("repo")), apply=bool(args.get("apply")))
    return ok(changed=bool(payload.get("changed")), warnings=[], compact=payload)


def aictx_messages_status(args: dict[str, Any]) -> dict[str, Any]:
    return ok(messages={"mode": get_message_mode(resolve_repo(args.get("repo")))})


def aictx_messages_set(args: dict[str, Any]) -> dict[str, Any]:
    mode = _text(args.get("mode"), "mode", required=True)
    if mode not in {MESSAGE_MODE_MUTED, MESSAGE_MODE_UNMUTED}:
        return error("invalid_mode", "mode must be muted or unmuted")
    return ok(changed=True, warnings=[], messages=set_message_mode(resolve_repo(args.get("repo")), mode))


def aictx_report_real_usage(args: dict[str, Any]) -> dict[str, Any]:
    from ..report import build_real_usage_report
    return ok(report=build_real_usage_report(resolve_repo(args.get("repo"))))


def call_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    func = globals().get(name)
    if not callable(func):
        return error("unknown_tool", f"Unknown tool: {name}")
    try:
        return func(args or {})
    except ValueError as exc:
        return error("invalid_request", str(exc))
    except Exception as exc:
        return error("tool_error", str(exc), {"tool": name})

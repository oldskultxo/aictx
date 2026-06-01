from __future__ import annotations

import copy
import fnmatch
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .continuity.quality import build_continuity_quality_issues
from .contract_compliance import load_persisted_resume_contract
from .lifecycle import build_lifecycle_status
from .work_state import load_active_work_state

GUARD_ACTIONS = {
    "before_first_edit",
    "edit",
    "risky_command",
    "finalize",
    "final_answer",
    "scope_change",
    "agent_switch",
    "continue_after_idle",
}
GUARD_RISKS = {"low", "normal", "high"}
_STALE_WORK_STATE_HOURS = 24
_QUALITY_CACHE_MAX = 16
_QUALITY_CACHE: dict[tuple[Any, ...], dict[str, Any]] = {}


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _parse_time(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _clean(value: Any, limit: int = 220) -> str:
    text = " ".join(str(value or "").strip().split())
    return text[:limit].rstrip()


def _warning(code: str, severity: str, message: str, *, check: str) -> dict[str, str]:
    return {
        "code": _clean(code, 80),
        "severity": severity if severity in {"info", "warning", "error"} else "warning",
        "message": _clean(message),
        "check": check,
    }


def _bump(checks: dict[str, str], key: str, severity: str) -> None:
    rank = {"ok": 0, "info": 0, "warning": 1, "error": 2}
    current = checks.get(key, "ok")
    if rank.get(severity, 1) > rank.get(current, 0):
        checks[key] = "error" if severity == "error" else "warning"


def _as_list(value: Any, limit: int = 12) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        text = _clean(item, 500)
        if text and text not in result:
            result.append(text)
        if len(result) >= limit:
            break
    return result


def _normalize_path(path: str) -> str:
    text = str(path or "").strip().replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    return text.strip("/")


def _path_matches(path: str, pattern: str) -> bool:
    candidate = _normalize_path(path)
    pat = _normalize_path(pattern)
    if not candidate or not pat:
        return False
    if pat.endswith("/**"):
        prefix = pat[:-3].strip("/")
        return candidate == prefix or candidate.startswith(prefix + "/")
    if any(ch in pat for ch in "*?[]"):
        return fnmatch.fnmatch(candidate, pat)
    return candidate == pat or candidate.startswith(pat.rstrip("/") + "/")


def _in_any_scope(path: str, patterns: list[str]) -> bool:
    return any(_path_matches(path, pattern) for pattern in patterns)


def _contract_scope(contract: dict[str, Any]) -> tuple[list[str], list[str]]:
    edit_scope = contract.get("edit_scope") if isinstance(contract.get("edit_scope"), dict) else {}
    allowed = _as_list(edit_scope.get("primary"), 24) + _as_list(edit_scope.get("secondary_if_needed"), 24)
    avoided = _as_list(edit_scope.get("avoid"), 24)
    expected = _as_list(contract.get("expected_first_files"), 6)
    first = contract.get("first_action") if isinstance(contract.get("first_action"), dict) else {}
    first_path = _clean(first.get("path"), 500)
    if first_path:
        allowed.append(first_path)
    allowed.extend(expected)
    return list(dict.fromkeys(allowed)), list(dict.fromkeys(avoided))




def _mtime_ns(path: Path) -> int:
    try:
        return path.stat().st_mtime_ns
    except OSError:
        return 0


def _quality_cache_key(repo: Path, task_goal: str, intent_text: str, active: dict[str, Any]) -> tuple[Any, ...]:
    rel_paths = (
        ".aictx/continuity/handoff.json",
        ".aictx/continuity/decisions.jsonl",
        ".aictx/failures/patterns.json",
        ".aictx/reports/continuity-view.md",
        ".aictx/repo_map/config.json",
        ".aictx/repo_map/status.json",
        ".aictx/repo_map/manifest.json",
    )
    return (
        id(build_continuity_quality_issues),
        repo.as_posix(),
        task_goal or intent_text,
        str(active.get("task_id") or "") if isinstance(active, dict) else "",
        str(active.get("updated_at") or "") if isinstance(active, dict) else "",
        tuple(_mtime_ns(repo / rel_path) for rel_path in rel_paths),
    )


def _cached_quality_issues(repo: Path, *, task_goal: str, intent_text: str, active: dict[str, Any]) -> dict[str, Any]:
    key = _quality_cache_key(repo, task_goal, intent_text, active)
    cached = _QUALITY_CACHE.get(key)
    if cached is not None:
        return copy.deepcopy(cached)
    quality_context = {"active_work_state": active} if isinstance(active, dict) else {}
    payload = build_continuity_quality_issues(repo, request_text=task_goal or intent_text, context=quality_context, limit=8)
    if len(_QUALITY_CACHE) >= _QUALITY_CACHE_MAX:
        _QUALITY_CACHE.pop(next(iter(_QUALITY_CACHE)))
    _QUALITY_CACHE[key] = copy.deepcopy(payload)
    return payload


def _validation_missing(contract: dict[str, Any], quality: dict[str, Any]) -> bool:
    issues = quality.get("issues") if isinstance(quality.get("issues"), list) else []
    validation_codes = {"missing_validation_evidence", "pending_validation_for_new_contract"}
    if any(isinstance(item, dict) and str(item.get("code") or "") in validation_codes for item in issues):
        return True
    test_command = contract.get("test_command") if isinstance(contract.get("test_command"), dict) else {}
    return bool(str(test_command.get("command") or "").strip())


def _destructive_command(command: str) -> bool:
    text = str(command or "").strip().lower()
    if not text:
        return False
    destructive = [
        r"\brm\s+-[^\n]*r",
        r"\bgit\s+reset\b",
        r"\bgit\s+clean\b",
        r"\bgit\s+push\b[^\n]*(--force|-f)",
        r"\bdrop\s+database\b",
        r"\btruncate\s+table\b",
        r"\bdelete\s+from\b",
    ]
    return any(re.search(pattern, text) for pattern in destructive)


def build_continuity_guard(
    repo_root: Path,
    *,
    action: str,
    paths: list[str] | None = None,
    command: str = "",
    intent: str = "",
    risk: str = "normal",
    agent_id: str = "",
    session_id: str = "",
) -> dict[str, Any]:
    repo = Path(repo_root).expanduser().resolve()
    action = str(action or "").strip()
    risk = str(risk or "normal").strip().lower() or "normal"
    if action not in GUARD_ACTIONS:
        raise ValueError("action must be one of: " + ", ".join(sorted(GUARD_ACTIONS)))
    if risk not in GUARD_RISKS:
        raise ValueError("risk must be one of: low, normal, high")

    requested_paths = [_normalize_path(path) for path in (paths or []) if _normalize_path(path)]
    intent_text = _clean(intent, 500)
    warnings: list[dict[str, str]] = []
    checks = {
        "work_state": "ok",
        "contract_alignment": "ok",
        "continuity_quality": "ok",
        "lifecycle": "ok",
        "validation": "ok",
    }

    active = load_active_work_state(repo)
    task_goal = str(active.get("goal") or intent_text or "") if isinstance(active, dict) else intent_text
    contract_source = load_persisted_resume_contract(repo, task_goal=task_goal, session_id=session_id)
    contract = contract_source.get("execution_contract") if isinstance(contract_source.get("execution_contract"), dict) else {}
    quality = _cached_quality_issues(repo, task_goal=task_goal, intent_text=intent_text, active=active if isinstance(active, dict) else {})
    lifecycle = build_lifecycle_status(repo, request_text=task_goal or intent_text, session_id=session_id, active_work_state=active if isinstance(active, dict) else None)

    if active:
        updated_at = _parse_time(active.get("updated_at"))
        if updated_at and updated_at < _now() - timedelta(hours=_STALE_WORK_STATE_HOURS):
            warnings.append(_warning("active_work_state_stale", "warning", "Active Work State appears stale.", check="work_state"))
            _bump(checks, "work_state", "warning")
        risks = _as_list(active.get("risks"), 3)
        if risks:
            warnings.append(_warning("work_state_risks_present", "warning", "Active Work State has open risks.", check="work_state"))
            _bump(checks, "work_state", "warning")
        active_files = _as_list(active.get("active_files"), 24)
        if action in {"edit", "scope_change"} and requested_paths and active_files:
            outside_active = [path for path in requested_paths if not _in_any_scope(path, active_files)]
            if outside_active:
                warnings.append(_warning("outside_work_state_files", "warning", "Requested path is outside active Work State files.", check="work_state"))
                _bump(checks, "work_state", "warning")
    elif action in {"continue_after_idle", "agent_switch"}:
        warnings.append(_warning("missing_active_work_state", "warning", "No active Work State is present for this boundary.", check="work_state"))
        _bump(checks, "work_state", "warning")

    if contract:
        allowed_scope, avoided_scope = _contract_scope(contract)
        first = contract.get("first_action") if isinstance(contract.get("first_action"), dict) else {}
        first_path = _normalize_path(str(first.get("path") or ""))
        if action == "before_first_edit" and first_path and requested_paths and not any(_path_matches(path, first_path) for path in requested_paths):
            warnings.append(_warning("first_action_mismatch", "warning", "Requested first edit boundary does not match the contract first action.", check="contract_alignment"))
            _bump(checks, "contract_alignment", "warning")
        if action in {"edit", "scope_change"} and requested_paths:
            outside = [path for path in requested_paths if allowed_scope and not _in_any_scope(path, allowed_scope)]
            avoided = [path for path in requested_paths if _in_any_scope(path, avoided_scope)]
            if outside:
                warnings.append(_warning("outside_expected_scope", "warning", "Requested path is outside current contract scope.", check="contract_alignment"))
                _bump(checks, "contract_alignment", "warning")
            if avoided:
                warnings.append(_warning("conflicts_with_avoid_scope", "error" if risk == "high" else "warning", "Requested path conflicts with contract avoid scope.", check="contract_alignment"))
                _bump(checks, "contract_alignment", "error" if risk == "high" else "warning")
    elif action in {"before_first_edit", "edit", "scope_change"}:
        warnings.append(_warning("missing_execution_contract", "warning", "No current execution contract was found.", check="contract_alignment"))
        _bump(checks, "contract_alignment", "warning")

    if action in {"finalize", "final_answer"} and _validation_missing(contract, quality):
        warnings.append(_warning("validation_evidence_missing", "warning", "Expected validation evidence is missing.", check="validation"))
        _bump(checks, "validation", "warning")

    quality_issues = [item for item in quality.get("issues", []) if isinstance(item, dict) and str(item.get("severity") or "") in {"warning", "error"}]
    for item in quality_issues[:3]:
        severity = "error" if str(item.get("severity") or "") == "error" else "warning"
        warnings.append(_warning(str(item.get("code") or "continuity_quality_warning"), severity, str(item.get("summary") or "Continuity quality warning."), check="continuity_quality"))
        _bump(checks, "continuity_quality", severity)

    lifecycle_warnings = lifecycle.get("warnings") if isinstance(lifecycle.get("warnings"), list) else []
    for item in lifecycle_warnings[:3]:
        if not isinstance(item, dict):
            continue
        warnings.append(_warning(str(item.get("code") or "lifecycle_warning"), "warning", str(item.get("summary") or "Lifecycle warning."), check="lifecycle"))
        _bump(checks, "lifecycle", "warning")
    if lifecycle.get("open_sessions") and action in {"agent_switch", "continue_after_idle"}:
        warnings.append(_warning("open_related_session", "warning", "Related open lifecycle session exists.", check="lifecycle"))
        _bump(checks, "lifecycle", "warning")

    if risk == "high" and action == "risky_command" and _destructive_command(command):
        warnings.append(_warning("destructive_high_risk_command", "error", "High-risk destructive command should not proceed without explicit confirmation.", check="contract_alignment"))
        _bump(checks, "contract_alignment", "error")

    # Dedupe by code/check while preserving order.
    deduped: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in warnings:
        key = (item["code"], item["check"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
        if len(deduped) >= 8:
            break
    warnings = deduped

    warning_count = sum(1 for item in warnings if item.get("severity") == "warning")
    error_count = sum(1 for item in warnings if item.get("severity") == "error")
    codes = {item.get("code") for item in warnings}
    if error_count:
        decision = "block"
    elif codes & {"active_work_state_stale", "validation_evidence_missing"} or checks["lifecycle"] == "warning" or warning_count >= 3:
        decision = "re_ground"
    elif warning_count:
        decision = "caution"
    else:
        decision = "allow"

    status = "error" if decision == "block" else "warning" if warnings else "ok"
    suggested = {
        "allow": "continue",
        "caution": "continue with caution",
        "re_ground": "run resume or prepare before continuing",
        "block": "stop and get explicit confirmation before continuing",
    }[decision]
    return {
        "status": status,
        "decision": decision,
        "warnings": warnings,
        "checks": checks,
        "suggested_next": suggested,
    }

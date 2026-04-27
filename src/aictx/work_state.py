from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .core_runtime import slugify
from .state import (
    REPO_TASKS_ACTIVE_PATH,
    REPO_TASKS_DIR,
    REPO_TASK_THREADS_DIR,
    append_jsonl,
    read_json,
    write_json,
)

WORK_STATE_VERSION = 1
_MAX_ITEMS = {
    "active_files": 12,
    "verified": 12,
    "unverified": 12,
    "discarded_paths": 12,
    "recommended_commands": 8,
    "risks": 8,
    "uncertainties": 8,
    "source_execution_ids": 12,
}
_ALLOWED_STATUS = {"in_progress", "resolved", "abandoned", "blocked", "paused"}
_LIST_FIELDS = {
    "active_files",
    "verified",
    "unverified",
    "discarded_paths",
    "recommended_commands",
    "risks",
    "source_execution_ids",
}
_STRING_FIELDS = {"task_id", "status", "goal", "current_hypothesis", "next_action", "created_at", "updated_at"}
_ALLOWED_FIELDS = _STRING_FIELDS | _LIST_FIELDS | {"version", "uncertainties"}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _truncate(value: Any, limit: int = 240) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def _dedupe_strings(values: Any, *, limit: int) -> list[str]:
    if not isinstance(values, list):
        return []
    seen: set[str] = set()
    cleaned: list[str] = []
    for item in values:
        text = _truncate(item)
        if not text or text in seen:
            continue
        seen.add(text)
        cleaned.append(text)
        if len(cleaned) >= limit:
            break
    return cleaned


def _normalize_uncertainty(item: Any) -> dict[str, str] | None:
    if isinstance(item, str):
        claim = _truncate(item)
        if not claim:
            return None
        return {"claim": claim, "confidence": "unknown", "needs_validation": ""}
    if not isinstance(item, dict):
        return None
    claim = _truncate(item.get("claim"))
    if not claim:
        return None
    confidence = str(item.get("confidence") or "unknown").strip().lower() or "unknown"
    needs_validation = _truncate(item.get("needs_validation"))
    return {
        "claim": claim,
        "confidence": confidence,
        "needs_validation": needs_validation,
    }


def _normalize_uncertainties(values: Any) -> list[dict[str, str]]:
    if not isinstance(values, list):
        return []
    seen: set[tuple[str, str, str]] = set()
    cleaned: list[dict[str, str]] = []
    for item in values:
        payload = _normalize_uncertainty(item)
        if not payload:
            continue
        key = (payload["claim"], payload["confidence"], payload["needs_validation"])
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(payload)
        if len(cleaned) >= _MAX_ITEMS["uncertainties"]:
            break
    return cleaned


def normalize_task_id(value: str) -> str:
    normalized = slugify(str(value or "")).replace("_", "-")[:80].strip("-_")
    return normalized or "task"


def _normalize_status(value: Any) -> str:
    status = str(value or "in_progress").strip().lower() or "in_progress"
    return status if status in _ALLOWED_STATUS else "in_progress"


def _run_git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )


def _normalize_git_context(payload: Any) -> dict[str, Any]:
    captured_at = now_iso()
    if not isinstance(payload, dict):
        return {}
    available = bool(payload.get("available"))
    if not available:
        reason = _truncate(payload.get("reason"), 80) or "git_unavailable"
        return {
            "available": False,
            "reason": reason,
            "captured_at": _truncate(payload.get("captured_at") or captured_at, 40),
        }
    branch = _truncate(payload.get("branch"), 240)
    head = _truncate(payload.get("head"), 80)
    changed_files = _dedupe_strings(payload.get("changed_files"), limit=64)
    return {
        "available": True,
        "branch": branch,
        "head": head,
        "dirty": bool(payload.get("dirty")),
        "changed_files": changed_files,
        "captured_at": _truncate(payload.get("captured_at") or captured_at, 40),
    }


def capture_git_context(repo_root: Path) -> dict[str, Any]:
    captured_at = now_iso()
    try:
        branch_result = _run_git(repo_root, "branch", "--show-current")
        head_result = _run_git(repo_root, "rev-parse", "HEAD")
        status_result = _run_git(repo_root, "status", "--porcelain")
    except (FileNotFoundError, OSError):
        return {
            "available": False,
            "reason": "git_unavailable",
            "captured_at": captured_at,
        }
    if branch_result.returncode != 0 or head_result.returncode != 0 or status_result.returncode != 0:
        return {
            "available": False,
            "reason": "git_unavailable",
            "captured_at": captured_at,
        }
    changed_files = []
    for line in status_result.stdout.splitlines():
        entry = line[3:].strip() if len(line) >= 4 else line.strip()
        if entry:
            changed_files.append(entry)
    return {
        "available": True,
        "branch": branch_result.stdout.strip(),
        "head": head_result.stdout.strip(),
        "dirty": bool(changed_files),
        "changed_files": _dedupe_strings(changed_files, limit=64),
        "captured_at": captured_at,
    }


def _is_git_ancestor(repo_root: Path, ancestor: str, head_ref: str = "HEAD") -> bool:
    if not ancestor.strip():
        return False
    try:
        result = _run_git(repo_root, "merge-base", "--is-ancestor", ancestor, head_ref)
    except (FileNotFoundError, OSError):
        return False
    return result.returncode == 0


def normalize_work_state(payload: dict[str, Any]) -> dict[str, Any]:
    payload = payload if isinstance(payload, dict) else {}
    created_at = _truncate(payload.get("created_at") or now_iso(), 40)
    updated_at = _truncate(payload.get("updated_at") or now_iso(), 40)
    task_id = normalize_task_id(str(payload.get("task_id") or payload.get("goal") or "task"))
    state = {
        "version": WORK_STATE_VERSION,
        "task_id": task_id,
        "status": _normalize_status(payload.get("status")),
        "goal": _truncate(payload.get("goal")),
        "current_hypothesis": _truncate(payload.get("current_hypothesis")),
        "active_files": _dedupe_strings(payload.get("active_files"), limit=_MAX_ITEMS["active_files"]),
        "verified": _dedupe_strings(payload.get("verified"), limit=_MAX_ITEMS["verified"]),
        "unverified": _dedupe_strings(payload.get("unverified"), limit=_MAX_ITEMS["unverified"]),
        "discarded_paths": _dedupe_strings(payload.get("discarded_paths"), limit=_MAX_ITEMS["discarded_paths"]),
        "uncertainties": _normalize_uncertainties(payload.get("uncertainties")),
        "next_action": _truncate(payload.get("next_action")),
        "recommended_commands": _dedupe_strings(payload.get("recommended_commands"), limit=_MAX_ITEMS["recommended_commands"]),
        "risks": _dedupe_strings(payload.get("risks"), limit=_MAX_ITEMS["risks"]),
        "source_execution_ids": _dedupe_strings(payload.get("source_execution_ids"), limit=_MAX_ITEMS["source_execution_ids"]),
        "created_at": created_at,
        "updated_at": updated_at,
    }
    git_context = _normalize_git_context(payload.get("git_context"))
    if git_context:
        state["git_context"] = git_context
    return state


def changed_work_state_fields(before: dict[str, Any], after: dict[str, Any], patch: dict[str, Any] | None = None) -> list[str]:
    patch_keys = set((patch or {}).keys())
    fields = sorted(
        field
        for field in _ALLOWED_FIELDS
        if field not in {"version", "task_id", "created_at", "updated_at"} and (before.get(field) != after.get(field) or field in patch_keys)
    )
    return fields


def work_state_paths(repo_root: Path, task_id: str | None = None) -> dict[str, Path]:
    base = Path(repo_root)
    normalized_task_id = normalize_task_id(task_id) if task_id else ""
    paths = {
        "tasks_dir": base / REPO_TASKS_DIR,
        "active": base / REPO_TASKS_ACTIVE_PATH,
        "threads_dir": base / REPO_TASK_THREADS_DIR,
    }
    if normalized_task_id:
        paths["thread"] = paths["threads_dir"] / f"{normalized_task_id}.json"
        paths["events"] = paths["threads_dir"] / f"{normalized_task_id}.events.jsonl"
    return paths


def load_active_task_id(repo_root: Path) -> str:
    payload = read_json(work_state_paths(repo_root)["active"], {})
    if not isinstance(payload, dict):
        return ""
    return normalize_task_id(str(payload.get("active_task_id") or "")) if str(payload.get("active_task_id") or "").strip() else ""


def load_work_state(repo_root: Path, task_id: str) -> dict[str, Any]:
    if not str(task_id or "").strip():
        return {}
    path = work_state_paths(repo_root, task_id).get("thread")
    if not isinstance(path, Path):
        return {}
    payload = read_json(path, {})
    if not isinstance(payload, dict) or not payload:
        return {}
    return normalize_work_state(payload)


def load_active_work_state(repo_root: Path) -> dict[str, Any]:
    task_id = load_active_task_id(repo_root)
    if not task_id:
        return {}
    return load_work_state(repo_root, task_id)


def evaluate_work_state_git_context(repo_root: Path, state: dict[str, Any]) -> dict[str, Any]:
    state = state if isinstance(state, dict) else {}
    saved_context = state.get("git_context") if isinstance(state.get("git_context"), dict) else None
    current_context = capture_git_context(repo_root)
    status = {
        "loadable": True,
        "reason": "no_git_context",
        "saved_branch": "",
        "current_branch": str(current_context.get("branch") or ""),
        "saved_head": "",
        "current_head": str(current_context.get("head") or ""),
        "warning": "",
    }
    if not saved_context:
        return status
    status["saved_branch"] = str(saved_context.get("branch") or "")
    status["saved_head"] = str(saved_context.get("head") or "")
    if not bool(saved_context.get("available")):
        status["reason"] = "git_unavailable"
        status["warning"] = "saved Work State git context unavailable; loading conservatively"
        return status
    if not bool(current_context.get("available")):
        status["reason"] = "git_unavailable"
        status["warning"] = "current repository git context unavailable; loading conservatively"
        return status
    saved_branch = status["saved_branch"]
    current_branch = status["current_branch"]
    saved_head = status["saved_head"]
    current_head = status["current_head"]
    saved_dirty = bool(saved_context.get("dirty"))
    current_dirty = bool(current_context.get("dirty"))
    if saved_branch == current_branch:
        status["reason"] = "same_branch"
        warnings: list[str] = []
        if saved_head and current_head and saved_head != current_head:
            warnings.append("same branch but HEAD changed since Work State was saved")
        if saved_dirty != current_dirty:
            warnings.append("working tree dirty state changed since Work State was saved")
        status["warning"] = "; ".join(warnings)
        return status
    if saved_dirty:
        status["loadable"] = False
        status["reason"] = "dirty_branch_mismatch"
        status["warning"] = "saved Work State was dirty on a different branch"
        return status
    if saved_head and _is_git_ancestor(repo_root, saved_head):
        status["reason"] = "branch_changed_but_merged"
        warnings = ["branch changed but saved commit is reachable from current HEAD"]
        if saved_dirty != current_dirty:
            warnings.append("working tree dirty state changed since Work State was saved")
        status["warning"] = "; ".join(warnings)
        return status
    status["loadable"] = False
    status["reason"] = "branch_mismatch_unmerged"
    status["warning"] = "saved branch differs and saved commit is not reachable from current HEAD"
    return status


def load_active_work_state_checked(repo_root: Path) -> dict[str, Any]:
    state = load_active_work_state(repo_root)
    if not state:
        return {
            "active_work_state": {},
            "work_state_git_status": {},
            "skipped_work_state": {},
        }
    status = evaluate_work_state_git_context(repo_root, state)
    if status.get("loadable"):
        return {
            "active_work_state": state,
            "work_state_git_status": status,
            "skipped_work_state": {},
        }
    return {
        "active_work_state": {},
        "work_state_git_status": status,
        "skipped_work_state": {
            "task_id": str(state.get("task_id") or ""),
            "reason": str(status.get("reason") or ""),
            "saved_branch": str(status.get("saved_branch") or ""),
            "current_branch": str(status.get("current_branch") or ""),
        },
    }


def list_work_states(repo_root: Path) -> list[dict[str, Any]]:
    threads_dir = work_state_paths(repo_root)["threads_dir"]
    if not threads_dir.exists():
        return []
    states: list[dict[str, Any]] = []
    for path in sorted(threads_dir.glob("*.json")):
        state = load_work_state(repo_root, path.stem)
        if state:
            states.append(state)
    states.sort(key=lambda row: (str(row.get("updated_at") or ""), str(row.get("task_id") or "")), reverse=True)
    return states


def load_recent_inactive_work_state(repo_root: Path, *, statuses: set[str] | None = None) -> dict[str, Any]:
    allowed = statuses or {"blocked", "paused"}
    for state in list_work_states(repo_root):
        if str(state.get("status") or "") in allowed:
            return state
    return {}


def _write_active_task(repo_root: Path, task_id: str) -> None:
    write_json(
        work_state_paths(repo_root)["active"],
        {
            "version": WORK_STATE_VERSION,
            "active_task_id": task_id,
            "updated_at": now_iso(),
        },
    )


def _event_row(state: dict[str, Any], *, source: str, event: str, fields: list[str] | None = None) -> dict[str, Any]:
    row = {
        "event": event,
        "task_id": str(state.get("task_id") or ""),
        "timestamp": now_iso(),
        "source": str(source or "cli") or "cli",
    }
    if fields:
        row["fields"] = list(fields)
    if event == "closed":
        row["status"] = str(state.get("status") or "")
    return row


def save_work_state(repo_root: Path, state: dict[str, Any], *, source: str, event: str = "updated") -> dict[str, Any]:
    normalized = normalize_work_state(state)
    paths = work_state_paths(repo_root, normalized["task_id"])
    previous = read_json(paths["thread"], {}) if isinstance(paths.get("thread"), Path) else {}
    if isinstance(previous, dict) and previous.get("created_at") and not normalized.get("created_at"):
        normalized["created_at"] = _truncate(previous.get("created_at"), 40)
    normalized["updated_at"] = now_iso()
    normalized["git_context"] = capture_git_context(repo_root)
    write_json(paths["thread"], normalized)
    if normalized.get("status") == "in_progress":
        _write_active_task(repo_root, normalized["task_id"])
    append_jsonl(
        paths["events"],
        _event_row(
            normalized,
            source=source,
            event=event,
            fields=sorted(key for key in normalized.keys() if key in _ALLOWED_FIELDS and key not in {"version", "task_id", "created_at", "updated_at"}),
        ),
    )
    return normalized


def start_work_state(
    repo_root: Path,
    goal: str,
    *,
    task_id: str | None = None,
    initial: dict[str, Any] | None = None,
    source: str = "cli",
) -> dict[str, Any]:
    payload = dict(initial or {})
    payload["goal"] = _truncate(goal)
    payload["task_id"] = normalize_task_id(task_id or payload.get("task_id") or goal)
    payload["status"] = "in_progress"
    timestamp = now_iso()
    payload["created_at"] = str(payload.get("created_at") or timestamp)
    payload["updated_at"] = timestamp
    return save_work_state(repo_root, payload, source=source, event="started")


def update_work_state(repo_root: Path, patch: dict[str, Any], *, task_id: str | None = None, source: str = "cli") -> dict[str, Any]:
    target_task_id = normalize_task_id(task_id or load_active_task_id(repo_root) or patch.get("task_id") or "task")
    current = load_work_state(repo_root, target_task_id)
    if not current:
        current = normalize_work_state({"task_id": target_task_id, "status": "in_progress"})
    merged = dict(current)
    patch = patch if isinstance(patch, dict) else {}
    for field in _STRING_FIELDS:
        if field in {"task_id", "created_at", "updated_at"}:
            continue
        if field in patch:
            merged[field] = patch.get(field)
    for field in _LIST_FIELDS:
        if field in patch:
            merged[field] = list(current.get(field, [])) + list(patch.get(field, []) or [])
    if "uncertainties" in patch:
        merged["uncertainties"] = list(current.get("uncertainties", [])) + list(patch.get("uncertainties", []) or [])
    merged["task_id"] = target_task_id
    merged["created_at"] = str(current.get("created_at") or now_iso())
    merged["updated_at"] = now_iso()
    if not merged.get("status"):
        merged["status"] = "in_progress"
    return save_work_state(repo_root, merged, source=source, event="updated")


def resume_work_state(repo_root: Path, task_id: str, *, source: str = "cli") -> dict[str, Any]:
    target_task_id = normalize_task_id(task_id)
    current = load_work_state(repo_root, target_task_id)
    if not current:
        return {}
    current["status"] = "in_progress"
    current["updated_at"] = now_iso()
    return save_work_state(repo_root, current, source=source, event="resumed")


def close_work_state(
    repo_root: Path,
    *,
    task_id: str | None = None,
    status: str = "resolved",
    patch: dict[str, Any] | None = None,
    source: str = "cli",
) -> dict[str, Any]:
    target_task_id = normalize_task_id(task_id or load_active_task_id(repo_root) or "task")
    current = load_work_state(repo_root, target_task_id)
    if not current:
        current = normalize_work_state({"task_id": target_task_id})
    patch = patch if isinstance(patch, dict) else {}
    for field in _STRING_FIELDS:
        if field in {"task_id", "created_at", "updated_at", "status"}:
            continue
        if field in patch:
            current[field] = patch.get(field)
    for field in _LIST_FIELDS:
        if field in patch:
            current[field] = list(current.get(field, [])) + list(patch.get(field, []) or [])
    if "uncertainties" in patch:
        current["uncertainties"] = list(current.get("uncertainties", [])) + list(patch.get("uncertainties", []) or [])
    current["status"] = status if status in _ALLOWED_STATUS else "resolved"
    current["updated_at"] = now_iso()
    normalized = save_work_state(repo_root, current, source=source, event="closed")
    write_json(
        work_state_paths(repo_root)["active"],
        {"version": WORK_STATE_VERSION, "active_task_id": "", "updated_at": now_iso()},
    )
    return normalized


def _command_to_recommendation(command: str) -> str:
    text = _truncate(command)
    lowered = text.lower()
    if any(token in lowered for token in ("pytest", " test", "make test", "make smoke", "ruff", "mypy", "pyright", "lint", "typecheck", "build")):
        return text
    return ""


def merge_work_state_from_execution(repo_root: Path, prepared: dict[str, Any], execution_log: dict[str, Any], result: dict[str, Any]) -> dict[str, Any] | None:
    active = load_active_work_state(repo_root)
    explicit = result.get("work_state") if isinstance(result.get("work_state"), dict) else {}
    if not active and not explicit:
        return None
    explicit_task_id = str(explicit.get("task_id") or "").strip() if isinstance(explicit, dict) else ""
    if not active and not explicit_task_id:
        return None
    target_task_id = explicit_task_id or str(active.get("task_id") or "")
    patch: dict[str, Any] = dict(explicit) if isinstance(explicit, dict) else {}
    active_files = []
    for field in ("files_opened", "files_edited", "files_reopened"):
        active_files.extend(list(execution_log.get(field, []) or []))
    if active_files:
        patch["active_files"] = list(patch.get("active_files", []) or []) + active_files
    execution_id = str(prepared.get("envelope", {}).get("execution_id") or "").strip()
    if execution_id:
        patch["source_execution_ids"] = list(patch.get("source_execution_ids", []) or []) + [execution_id]
    recommended_commands = []
    for command in list(execution_log.get("commands_executed", []) or []) + list(execution_log.get("tests_executed", []) or []):
        recommendation = _command_to_recommendation(str(command or ""))
        if recommendation:
            recommended_commands.append(recommendation)
    if recommended_commands:
        patch["recommended_commands"] = list(patch.get("recommended_commands", []) or []) + recommended_commands
    if bool(result.get("success")):
        verified: list[str] = []
        for command in list(execution_log.get("commands_executed", []) or []):
            text = _truncate(command)
            if text:
                verified.append(f"Command succeeded: {text}")
        for command in list(execution_log.get("tests_executed", []) or []):
            text = _truncate(command)
            if text:
                verified.append(f"Test command passed: {text}")
        if verified:
            patch["verified"] = list(patch.get("verified", []) or []) + verified
    else:
        risks = []
        for item in list(execution_log.get("notable_errors", []) or []):
            text = _truncate(item)
            if text:
                risks.append(f"Observed error: {text}")
        if risks:
            patch["risks"] = list(patch.get("risks", []) or []) + risks
    if not patch:
        return None
    return update_work_state(repo_root, patch, task_id=target_task_id, source="finalize_execution")


def compact_work_state_for_prepare(state: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(state, dict) or not state:
        return {}
    normalized = normalize_work_state(state)
    has_signal = any(
        [
            normalized.get("goal"),
            normalized.get("current_hypothesis"),
            normalized.get("next_action"),
            normalized.get("active_files"),
            normalized.get("verified"),
            normalized.get("unverified"),
            normalized.get("recommended_commands"),
            normalized.get("risks"),
        ]
    )
    if not has_signal:
        return {}
    compact = {
        "task_id": normalized.get("task_id", ""),
        "status": normalized.get("status", ""),
        "goal": normalized.get("goal", ""),
        "current_hypothesis": normalized.get("current_hypothesis", ""),
        "active_files": list(normalized.get("active_files", []))[:5],
        "verified": list(normalized.get("verified", []))[:4],
        "unverified": list(normalized.get("unverified", []))[:4],
        "next_action": normalized.get("next_action", ""),
        "recommended_commands": list(normalized.get("recommended_commands", []))[:4],
        "risks": list(normalized.get("risks", []))[:4],
        "updated_at": normalized.get("updated_at", ""),
    }
    return {key: value for key, value in compact.items() if value not in ("", [], None)}


def render_work_state_summary(state: dict[str, Any]) -> str:
    compact = compact_work_state_for_prepare(state)
    if not compact:
        return ""
    goal = str(compact.get("goal") or compact.get("task_id") or "").strip()
    next_action = str(compact.get("next_action") or "").strip()
    hypothesis = str(compact.get("current_hypothesis") or "").strip()
    parts = [goal]
    if next_action:
        parts.append(f"Next: {next_action}")
    if hypothesis and len(hypothesis) <= 120:
        parts.append(f"Hypothesis: {hypothesis}")
    return ". ".join(part.rstrip(".") for part in parts if part).strip() + "."

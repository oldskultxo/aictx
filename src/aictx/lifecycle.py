from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .contract_compliance import load_contract_compliance_history
from .state import REPO_CONTINUITY_DIR, append_jsonl, read_json, read_jsonl
from .work_state import load_active_work_state

LIFECYCLE_EVENTS_PATH = REPO_CONTINUITY_DIR / "lifecycle_events.jsonl"
HANDOFF_PATH = REPO_CONTINUITY_DIR / "handoff.json"
LIFECYCLE_SCHEMA_VERSION = "1.0"
RESUME_FINALIZE_HOURS = 2
STALE_WORK_STATE_HOURS = 24


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_time(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _clean(value: Any, limit: int = 240) -> str:
    text = str(value or "").strip()
    return text[:limit].rstrip()


def _count(values: Any) -> int:
    return len(values) if isinstance(values, list) else int(values or 0) if isinstance(values, int) else 0


def _terms(text: str) -> set[str]:
    return {token for token in re.split(r"[^a-z0-9_]+", str(text or "").lower()) if len(token) >= 4}


def _related(request_text: str, session_id: str, event: dict[str, Any]) -> bool:
    if session_id and session_id == str(event.get("session_id") or ""):
        return True
    request_terms = _terms(request_text)
    if not request_terms:
        return True
    return bool(request_terms & _terms(str(event.get("task") or "")))


def append_lifecycle_event(repo_root: Path, event: dict[str, Any]) -> dict[str, Any]:
    repo = Path(repo_root).expanduser().resolve()
    row = {
        "schema_version": LIFECYCLE_SCHEMA_VERSION,
        "event_type": _clean(event.get("event_type"), 80),
        "timestamp": _clean(event.get("timestamp") or _iso(_now()), 40),
        "source": _clean(event.get("source") or "cli", 20),
        "agent_id": _clean(event.get("agent_id"), 80),
        "adapter_id": _clean(event.get("adapter_id"), 80),
        "session_id": _clean(event.get("session_id"), 120),
        "execution_id": _clean(event.get("execution_id"), 120),
        "task": _clean(event.get("task"), 500),
        "task_type": _clean(event.get("task_type"), 80),
        "contract_id": _clean(event.get("contract_id"), 120),
        "work_state_task_id": _clean(event.get("work_state_task_id"), 120),
        "status": _clean(event.get("status"), 40),
        "files_opened_count": _count(event.get("files_opened_count")),
        "files_edited_count": _count(event.get("files_edited_count")),
        "commands_count": _count(event.get("commands_count")),
        "tests_count": _count(event.get("tests_count")),
    }
    row = {key: value for key, value in row.items() if value not in ("", None)}
    append_jsonl(repo / LIFECYCLE_EVENTS_PATH, row)
    return row


def load_lifecycle_events(repo_root: Path, limit: int = 500) -> list[dict[str, Any]]:
    return read_jsonl(Path(repo_root).expanduser().resolve() / LIFECYCLE_EVENTS_PATH)[-max(1, int(limit or 1)) :]


def _session_key(event: dict[str, Any]) -> str:
    return str(event.get("session_id") or event.get("execution_id") or f"{event.get('agent_id') or 'agent'}:{event.get('task') or ''}")


def _warning(code: str, summary: str, event: dict[str, Any], suggested: str) -> dict[str, str]:
    return {
        "code": code,
        "severity": "warning",
        "summary": summary,
        "session_id": str(event.get("session_id") or ""),
        "task": str(event.get("task") or ""),
        "suggested_next_action": suggested,
    }


def _contract_evaluated(repo: Path, contract_id: str) -> bool:
    if not contract_id:
        return True
    for row in load_contract_compliance_history(repo, limit=500):
        if str(row.get("contract_id") or "") == contract_id and str(row.get("status") or "") != "not_evaluated":
            return True
    return False


def _has_recent_finalize(finalizes: list[dict[str, Any]], task: str, cutoff: datetime) -> bool:
    task_terms = _terms(task)
    for event in reversed(finalizes):
        finalized_at = _parse_time(event.get("timestamp"))
        if not finalized_at or finalized_at < cutoff:
            continue
        if not task_terms or task_terms & _terms(str(event.get("task") or "")):
            return True
    return False


def build_lifecycle_status(repo_root: Path, *, request_text: str = "", session_id: str = "", now: datetime | None = None) -> dict[str, Any]:
    repo = Path(repo_root).expanduser().resolve()
    current = (now or _now()).astimezone(timezone.utc).replace(microsecond=0)
    resume_cutoff = current - timedelta(hours=RESUME_FINALIZE_HOURS)
    stale_cutoff = current - timedelta(hours=STALE_WORK_STATE_HOURS)
    events = load_lifecycle_events(repo)
    finalizes = [event for event in events if event.get("event_type") == "finalize_called"]
    warnings: list[dict[str, str]] = []
    open_sessions: list[dict[str, Any]] = []

    latest_by_session: dict[str, dict[str, Any]] = {}
    for event in events:
        key = _session_key(event)
        if event.get("event_type") == "resume_called":
            latest_by_session[key] = event

    for key, resume in latest_by_session.items():
        resumed_at = _parse_time(resume.get("timestamp"))
        if not resumed_at or resumed_at > resume_cutoff:
            continue
        matched_finalize = False
        for finalize in finalizes:
            finalized_at = _parse_time(finalize.get("timestamp"))
            if not finalized_at or finalized_at < resumed_at:
                continue
            if _session_key(finalize) == key or (
                str(finalize.get("agent_id") or "") == str(resume.get("agent_id") or "")
                and _terms(str(finalize.get("task") or "")) & _terms(str(resume.get("task") or ""))
            ):
                matched_finalize = True
                break
        if matched_finalize:
            continue
        row = {
            "session_id": str(resume.get("session_id") or ""),
            "started": str(resume.get("timestamp") or ""),
            "task": str(resume.get("task") or ""),
            "status": "resume_called, finalize_missing",
            "source": str(resume.get("source") or ""),
        }
        open_sessions.append(row)
        if _related(request_text, session_id, resume):
            code = "readonly_mcp_only" if str(resume.get("source") or "") == "mcp" else "session_started_but_not_finalized"
            summary = "MCP readonly lifecycle started but finalize was not observed." if code == "readonly_mcp_only" else "Session started with resume but finalize was not observed."
            warnings.append(_warning(code, summary, resume, "Run `aictx finalize` or resume the open Work State before starting unrelated work."))
            if not _contract_evaluated(repo, str(resume.get("contract_id") or "")):
                warnings.append(_warning("contract_generated_not_evaluated", "Execution contract was generated but not evaluated.", resume, "Finalize the session with observed files, commands and tests."))

    for finalize in finalizes[-50:]:
        if str(finalize.get("status") or "") == "success" and int(finalize.get("files_edited_count") or 0) > 0 and int(finalize.get("commands_count") or 0) == 0 and int(finalize.get("tests_count") or 0) == 0:
            if _related(request_text, session_id, finalize):
                warnings.append(_warning("changes_without_evidence", "Changes were finalized without command or test evidence.", finalize, "Record commands/tests in `aictx finalize` when work changes files."))
                warnings.append(_warning("validation_evidence_missing", "Validation evidence is missing for a completed task.", finalize, "Run and record the focused validation command."))

    active = load_active_work_state(repo)
    active_updated = _parse_time(active.get("updated_at")) if isinstance(active, dict) else None
    if active and active_updated and active_updated < stale_cutoff:
        probe = {"session_id": "", "task": str(active.get("goal") or active.get("task_id") or "")}
        if _related(request_text, session_id, probe) and not _has_recent_finalize(finalizes, str(probe.get("task") or ""), stale_cutoff):
            warnings.append(_warning("active_work_state_no_recent_finalization", "Active Work State has no recent finalization.", probe, "Resume or close the active Work State before starting unrelated work."))

    handoff = read_json(repo / HANDOFF_PATH, {})
    handoff_time = _parse_time(handoff.get("updated_at") or handoff.get("timestamp")) if isinstance(handoff, dict) else None
    if handoff and handoff_time and handoff_time < stale_cutoff:
        probe = {"session_id": str(handoff.get("source_execution_id") or ""), "task": str(handoff.get("summary") or "")}
        if _related(request_text, session_id, probe) and not _has_recent_finalize(finalizes, str(probe.get("task") or ""), stale_cutoff):
            warnings.append(_warning("stale_active_task_or_handoff", "Handoff appears stale and has no recent matching finalization.", probe, "Verify the handoff against current files before relying on it."))

    deduped: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in warnings:
        key = (item["code"], item.get("session_id", ""), item.get("task", ""))
        if key not in seen:
            seen.add(key)
            deduped.append(item)
        if len(deduped) >= 12:
            break
    return {
        "schema_version": "1.0",
        "status": "warning" if deduped else "ok",
        "open_sessions": open_sessions[:12],
        "warnings": deduped,
        "thresholds": {"resume_finalize_hours": RESUME_FINALIZE_HOURS, "stale_work_state_hours": STALE_WORK_STATE_HOURS},
    }

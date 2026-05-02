from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .failure_memory import FAILURE_PATTERNS_PATH, lookup_failures
from .state import (
    REPO_CONTINUITY_DIR,
    REPO_CONTINUITY_SESSION_PATH,
    REPO_MEMORY_DIR,
    append_jsonl,
    read_json,
    read_jsonl,
    touch_session_identity,
    write_json,
)
from .strategy_memory import load_strategies, select_strategy, strategy_reuse_confidence
from .work_state import compact_work_state_for_prepare, load_active_work_state, load_recent_inactive_work_state

HANDOFF_PATH = REPO_CONTINUITY_DIR / "handoff.json"
HANDOFFS_HISTORY_PATH = REPO_CONTINUITY_DIR / "handoffs.jsonl"
DECISIONS_PATH = REPO_CONTINUITY_DIR / "decisions.jsonl"
SEMANTIC_REPO_PATH = REPO_CONTINUITY_DIR / "semantic_repo.json"
DEDUPE_REPORT_PATH = REPO_CONTINUITY_DIR / "dedupe_report.json"
STALENESS_PATH = REPO_CONTINUITY_DIR / "staleness.json"
CONTINUITY_METRICS_PATH = REPO_CONTINUITY_DIR / "continuity_metrics.json"
LAST_EXECUTION_SUMMARY_PATH = REPO_CONTINUITY_DIR / "last_execution_summary.md"
RESUME_CAPSULE_MARKDOWN_PATH = REPO_CONTINUITY_DIR / "resume_capsule.md"
RESUME_CAPSULE_JSON_PATH = REPO_CONTINUITY_DIR / "resume_capsule.json"
AICTX_TEXT_SEPARATOR = "────────────────────────────────"


def append_aictx_text_separator(text: str) -> str:
    cleaned = str(text or "").rstrip()
    if not cleaned:
        return ""
    if cleaned.endswith(AICTX_TEXT_SEPARATOR):
        return f"{cleaned}\n\n"
    return f"{cleaned}\n\n{AICTX_TEXT_SEPARATOR}\n\n"


def _read_optional_json(repo_root: Path, relative_path: Path, expected_type: type, warnings: list[str]) -> Any:
    path = repo_root / relative_path
    if not path.exists():
        return {} if expected_type is dict else []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        warnings.append(f"malformed:{relative_path.as_posix()}")
        return {} if expected_type is dict else []
    if not isinstance(payload, expected_type):
        warnings.append(f"invalid_type:{relative_path.as_posix()}")
        return {} if expected_type is dict else []
    return payload


def _read_optional_jsonl(repo_root: Path, relative_path: Path, warnings: list[str]) -> list[dict[str, Any]]:
    path = repo_root / relative_path
    if not path.exists():
        return []
    rows = read_jsonl(path)
    invalid_lines = 0
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        warnings.append(f"unreadable:{relative_path.as_posix()}")
        return rows
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            invalid_lines += 1
            continue
        if not isinstance(payload, dict):
            invalid_lines += 1
    if invalid_lines:
        warnings.append(f"invalid_jsonl_lines:{relative_path.as_posix()}:{invalid_lines}")
    return rows


def _session_from_payload(session_identity: dict[str, Any] | None, repo_root: Path, warnings: list[str]) -> dict[str, Any]:
    if isinstance(session_identity, dict):
        session = session_identity.get("session")
        if isinstance(session, dict):
            extra_warnings = session_identity.get("warnings")
            if isinstance(extra_warnings, list):
                warnings.extend(str(item) for item in extra_warnings if str(item).strip())
            return dict(session)
    return _read_optional_json(repo_root, REPO_CONTINUITY_SESSION_PATH, dict, warnings)


def _session_summary_parts(session: dict[str, Any], repo_root: Path) -> tuple[str, int]:
    runtime = str(session.get("runtime") or "agent").strip() or "agent"
    repo_id = str(session.get("repo_id") or repo_root.name).strip() or repo_root.name
    agent_label = str(session.get("agent_label") or f"{runtime}@{repo_id}").strip() or f"{runtime}@{repo_id}"
    try:
        session_count = int(session.get("session_count") or 0)
    except (TypeError, ValueError):
        session_count = 0
    return agent_label, max(session_count, 0)


def _canonical_banner_header(agent_label: str, session_count: int) -> str:
    return f"{agent_label} · session #{session_count} · awake"


def _banner_header(agent_label: str, session_count: int) -> str:
    return _canonical_banner_header(agent_label, session_count)


def _compact_banner_text(text: str, *, max_len: int = 88) -> str:
    compact = " ".join(str(text or "").strip().split()).rstrip(". ")
    for prefix in (
        "Phase 1 complete:",
        "Phase 1 completed:",
        "Phase 2 complete:",
        "Phase 2 completed:",
        "Phase 3 complete:",
        "Phase 3 completed:",
        "Phase 4 complete:",
        "Phase 4 completed:",
        "Final phase executed:",
    ):
        if compact.startswith(prefix):
            compact = compact[len(prefix):].strip().rstrip(". ")
            break
    if len(compact) <= max_len:
        return compact
    shortened = compact[: max_len - 1].rsplit(" ", 1)[0].strip()
    return (shortened or compact[: max_len - 1].strip()) + "…"


def _compact_topic(row: dict[str, Any]) -> str:
    for key in ("reason", "summary", "task_type"):
        value = _compact_banner_text(str(row.get(key) or ""), max_len=120)
        if value:
            return value
    return "previous work"


def _compact_progress(row: dict[str, Any]) -> str:
    items = [_compact_banner_text(item, max_len=220) for item in _clean_string_list(row.get("completed"), limit=3)]
    items = [item for item in items if item]
    if items:
        return ", ".join(items)
    return _compact_banner_text(str(row.get("summary") or ""), max_len=240) or "previous work"


def _compact_blocker(row: dict[str, Any]) -> str:
    items = [_compact_banner_text(item, max_len=88) for item in _clean_string_list(row.get("blocked"), limit=2)]
    items = [item for item in items if item]
    if items:
        return ", ".join(items)
    return _compact_banner_text(str(row.get("summary") or ""), max_len=120) or "previous work"


def _next_focus(row: dict[str, Any]) -> str:
    for key in ("next_steps", "open_items", "blocked"):
        items = _clean_string_list(row.get(key), limit=1)
        if items:
            return items[0]
    return ""


def _entry_point_focus(row: dict[str, Any]) -> str:
    points = _clean_string_list(row.get("recommended_starting_points"), limit=1)
    return points[0] if points else ""


def _entry_point_is_redundant(row: dict[str, Any], entry_point: str) -> bool:
    if not entry_point:
        return False
    points = _clean_string_list(row.get("recommended_starting_points"), limit=2)
    if len(points) != 1:
        return False
    topic = _compact_topic(row)
    progress = _compact_progress(row)
    needle = entry_point.casefold()
    return needle in topic.casefold() or needle in progress.casefold()


def _active_work_state_payload(context: dict[str, Any]) -> dict[str, str]:
    state = context.get("active_work_state") if isinstance(context.get("active_work_state"), dict) else {}
    if not state:
        return {}
    goal = _compact_banner_text(str(state.get("goal") or state.get("task_id") or ""), max_len=96)
    next_action = _compact_banner_text(str(state.get("next_action") or ""), max_len=96)
    if not goal:
        return {}
    return {"goal": goal, "next_action": next_action}


def _active_work_state_line(context: dict[str, Any]) -> str:
    payload = _active_work_state_payload(context)
    if not payload:
        return ""
    line = f"Active task: {payload['goal']}."
    if payload.get("next_action"):
        line += f" Next: {payload['next_action']}."
    return line


def render_continuity_summary(context: dict[str, Any], repo_root: Path) -> str:
    session = context.get("session") if isinstance(context.get("session"), dict) else {}
    loaded = context.get("loaded") if isinstance(context.get("loaded"), dict) else {}
    agent_label, session_count = _session_summary_parts(session, repo_root)
    lines = [
        _banner_header(agent_label, session_count),
        "",
        "Loaded:",
        f"- handoff: {'yes' if loaded.get('handoff') else 'no'}",
        f"- decisions: {'yes' if loaded.get('decisions') else 'no'}",
        f"- failures: {'yes' if loaded.get('failures') else 'no'}",
        f"- preferences: {'yes' if loaded.get('preferences') else 'no'}",
        f"- semantic_repo: {'yes' if loaded.get('semantic_repo') else 'no'}",
        f"- procedural_reuse: {'yes' if loaded.get('procedural_reuse') else 'no'}",
    ]
    if "work_state" in loaded:
        lines.append(f"- work_state: {'yes' if loaded.get('work_state') else 'no'}")
    return "\n".join(lines)


def build_startup_banner_render_payload(context: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    session = context.get("session") if isinstance(context.get("session"), dict) else {}
    agent_label, session_count = _session_summary_parts(session, repo_root)
    header = _banner_header(agent_label, session_count)
    latest = latest_handoff_record(repo_root)
    lines: list[dict[str, Any]] = []
    if not latest:
        lines.append({
            "kind": "no_previous_handoff",
            "canonical_text": "No previous handoff to resume.",
            "message": "No previous handoff to resume.",
        })
    else:
        topic = _compact_topic(latest)
        lines.append({
            "kind": "resuming",
            "canonical_text": f"Resuming: {topic}.",
            "topic": topic,
        })
        status = str(latest.get("status") or "").strip().lower()
        if status in {"failed", "unresolved", "blocked"}:
            blocker = _compact_blocker(latest)
            lines.append({
                "kind": "blocked",
                "canonical_text": f"Blocked: {blocker}.",
                "status": status or "blocked",
                "blocker": blocker,
            })
        else:
            progress = _compact_progress(latest)
            lines.append({
                "kind": "last_progress",
                "canonical_text": f"Last progress: {progress}.",
                "progress": progress,
            })
        next_focus = _next_focus(latest)
        if next_focus:
            lines.append({
                "kind": "next",
                "canonical_text": f"Next: {next_focus}",
                "items": [next_focus],
            })
        else:
            entry_point = _entry_point_focus(latest)
            if entry_point and not _entry_point_is_redundant(latest, entry_point):
                lines.append({
                    "kind": "entry_point",
                    "canonical_text": f"Entry point: {entry_point}",
                    "paths": [entry_point],
                })
    work_payload = _active_work_state_payload(context)
    if work_payload:
        work_line = f"Active task: {work_payload['goal']}."
        if work_payload.get("next_action"):
            work_line += f" Next: {work_payload['next_action']}."
        lines.append({
            "kind": "active_task",
            "canonical_text": work_line,
            "goal": work_payload["goal"],
            "next_action": work_payload.get("next_action", ""),
        })
    rendered_lines = lines[:4]
    return {
        "header": {
            "agent_label": agent_label,
            "session_count": session_count,
            "canonical_text": header,
        },
        "lines": rendered_lines,
        "canonical_text": append_aictx_text_separator(
            header + "\n\n" + "\n".join(str(item.get("canonical_text") or "") for item in rendered_lines)
        ),
    }


def render_startup_banner(context: dict[str, Any], repo_root: Path) -> str:
    payload = build_startup_banner_render_payload(context, repo_root)
    return append_aictx_text_separator(str(payload.get("canonical_text") or ""))


def _summary_next_points(summary: dict[str, Any], *, limit: int = 2) -> list[str]:
    handoff = summary.get("handoff_payload") if isinstance(summary.get("handoff_payload"), dict) else {}
    points = handoff.get("recommended_starting_points")
    if not isinstance(points, list):
        points = handoff.get("next_steps", [])
    return _clean_string_list(points, limit=limit)


def render_last_execution_summary_markdown(summary: dict[str, Any]) -> str:
    reused = "yes" if summary.get("strategy_reused") else "no"
    reason = str(summary.get("selection_reason") or "").strip() or "none"
    strategy_points = summary.get("strategy_entry_points") if isinstance(summary.get("strategy_entry_points"), list) else []
    avoided = summary.get("avoided") if isinstance(summary.get("avoided"), list) else []
    continuity_value = summary.get("continuity_value") if isinstance(summary.get("continuity_value"), dict) else {}
    repo_map = summary.get("repo_map_status") if isinstance(summary.get("repo_map_status"), dict) else {}
    lines = [
        "# AICTX Execution Summary",
        "",
        "## Continuity",
        f"- Prepared task type: {str(summary.get('prepared_task_type') or 'unknown')}",
        f"- Final task type: {str(summary.get('final_task_type') or 'unknown')}",
        f"- Effective task type: {str(summary.get('effective_task_type') or 'unknown')}",
        f"- Prepared area: {str(summary.get('prepared_area_id') or 'unknown')}",
        f"- Final area: {str(summary.get('final_area_id') or 'unknown')}",
        f"- Effective area: {str(summary.get('effective_area_id') or 'unknown')}",
        f"- Reused strategy: {reused}",
        f"- Strategy reason: {reason}",
        f"- Strategy entry points: {', '.join(str(item) for item in strategy_points[:4]) if strategy_points else 'none'}",
        f"- Reuse confidence: {str(summary.get('reuse_confidence') or 'low')}",
        f"- Handoff stored: {'yes' if summary.get('handoff_stored') else 'no'}",
        f"- Decision stored: {'yes' if summary.get('decision_stored') else 'no'}",
        f"- Failure pattern recorded: {'yes' if summary.get('failure_recorded') else 'no'}",
    ]
    if avoided:
        lines.append(f"- Avoided issues: {', '.join(str(item) for item in avoided[:4])}")
    if continuity_value:
        loaded_sources = continuity_value.get("loaded_sources") if isinstance(continuity_value.get("loaded_sources"), list) else []
        if loaded_sources:
            lines.append(f"- AICTX value sources: {', '.join(str(item) for item in loaded_sources[:6])}")
    if repo_map:
        lines.append(
            f"- RepoMap: enabled={'yes' if repo_map.get('enabled') else 'no'}, used={'yes' if repo_map.get('used') else 'no'}, status={str(repo_map.get('refresh_status') or 'unknown')}"
        )
    work_state_updated = summary.get("work_state_updated") if isinstance(summary.get("work_state_updated"), dict) else {}
    if work_state_updated.get("updated"):
        task_id = str(work_state_updated.get("task_id") or "").strip() or "unknown"
        fields = work_state_updated.get("fields") if isinstance(work_state_updated.get("fields"), list) else []
        field_text = ", ".join(str(item) for item in fields[:5]) if fields else "none"
        lines.append(f"- Work state updated: {task_id} ({field_text})")
    next_guidance = summary.get("next_guidance") if isinstance(summary.get("next_guidance"), dict) else {}
    if next_guidance:
        lines.extend(["", "## AICTX next", ""])
        rendered = render_next_text(next_guidance)
        lines.extend(rendered.splitlines()[1:] if rendered.startswith("AICTX next") else rendered.splitlines())
    observed_lines: list[str] = []
    files_observed = int(summary.get('files_opened', 0) or 0)
    if files_observed:
        observed_lines.append(f"- Files observed: {files_observed}")
    tests = summary.get("tests_observed") if isinstance(summary.get("tests_observed"), list) else []
    if tests:
        observed_lines.append("- Tests observed:")
        observed_lines.extend([f"  - {item}" for item in _clean_string_list(tests, limit=8)])
    if observed_lines:
        lines.extend(["", "## Observed execution"])
        lines.extend(observed_lines)
    lines.extend(["", "## Next session", "", "Recommended starting points:"])
    points = _summary_next_points(summary, limit=5)
    if points:
        lines.extend([f"- {item}" for item in points])
    else:
        lines.append("- none")
    raw_lines = [
        f"- Learning stored: {'yes' if summary.get('learning_persisted') else 'no'}",
        f"- Strategy stored: {'yes' if summary.get('strategy_persisted') else 'no'}",
    ]
    commands_count = len(summary.get('commands_observed', [])) if isinstance(summary.get('commands_observed'), list) else 0
    reopened_count = int(summary.get('reopened_files', 0) or 0)
    if commands_count:
        raw_lines.append(f"- Commands observed: {commands_count}")
    if reopened_count:
        raw_lines.append(f"- Reopened files: {reopened_count}")
    lines.extend(["", "## Raw details", ""] + raw_lines)
    return "\n".join(lines) + "\n"


def write_last_execution_summary(repo_root: Path, summary: dict[str, Any]) -> dict[str, Any]:
    path = repo_root / LAST_EXECUTION_SUMMARY_PATH
    write_text = render_last_execution_summary_markdown(summary)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(write_text, encoding="utf-8")
    return {"path": path.as_posix(), "bytes": len(write_text.encode("utf-8"))}


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    payload = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows if isinstance(row, dict))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text((payload + "\n") if payload else "", encoding="utf-8")


def _normalize_handoff_history_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "execution_id": str(row.get("execution_id") or "").strip(),
        "timestamp": str(row.get("timestamp") or "").strip(),
        "summary": str(row.get("summary") or "").strip(),
        "status": str(row.get("status") or "").strip(),
        "reason": str(row.get("reason") or "").strip(),
        "task_type": str(row.get("task_type") or "").strip(),
        "completed": _clean_string_list(row.get("completed"), limit=5),
        "next_steps": _clean_string_list(row.get("next_steps"), limit=5),
        "blocked": _clean_string_list(row.get("blocked"), limit=5),
        "risks": _clean_string_list(row.get("risks"), limit=5),
        "recommended_starting_points": _clean_string_list(row.get("recommended_starting_points"), limit=5),
        "files_observed": int(row.get("files_observed", 0) or 0),
        "tests_observed": _clean_string_list(row.get("tests_observed"), limit=8),
    }


def load_handoff_history(repo_root: Path, limit: int = 10) -> list[dict[str, Any]]:
    rows = read_jsonl(repo_root / HANDOFFS_HISTORY_PATH)
    normalized = [_normalize_handoff_history_row(row) for row in rows if isinstance(row, dict)]
    cap = max(0, int(limit or 0))
    return normalized[-cap:] if cap else normalized


def append_handoff_history(repo_root: Path, handoff_record: dict[str, Any], limit: int = 10) -> dict[str, Any]:
    rows = load_handoff_history(repo_root, limit=0)
    rows.append(_normalize_handoff_history_row(handoff_record))
    cap = max(1, int(limit or 10))
    capped = rows[-cap:]
    _write_jsonl(repo_root / HANDOFFS_HISTORY_PATH, capped)
    return {"path": (repo_root / HANDOFFS_HISTORY_PATH).as_posix(), "count": len(capped)}


def latest_handoff_record(repo_root: Path) -> dict[str, Any]:
    rows = load_handoff_history(repo_root, limit=1)
    if rows:
        return rows[-1]
    fallback = read_json(repo_root / HANDOFF_PATH, {})
    if not isinstance(fallback, dict) or not fallback:
        return {}
    return {
        "execution_id": str(fallback.get("source_execution_id") or "").strip(),
        "timestamp": str(fallback.get("updated_at") or "").strip(),
        "summary": str(fallback.get("summary") or "").strip(),
        "status": "resolved",
        "reason": "",
        "task_type": "",
        "completed": _clean_string_list(fallback.get("completed"), limit=5),
        "next_steps": _clean_string_list(fallback.get("next_steps"), limit=5),
        "blocked": _clean_string_list(fallback.get("blocked") or fallback.get("open_items"), limit=5),
        "recommended_starting_points": _clean_string_list(fallback.get("recommended_starting_points"), limit=5),
        "files_observed": 0,
        "tests_observed": [],
    }


def _clean_string_list(values: Any, *, limit: int = 8) -> list[str]:
    if not isinstance(values, list):
        return []
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = str(value or "").strip()
        if not item or item in seen:
            continue
        cleaned.append(item)
        seen.add(item)
        if len(cleaned) >= limit:
            break
    return cleaned


def _decision_signature(decision: dict[str, Any]) -> tuple[Any, ...]:
    return (
        str(decision.get("decision") or "").strip(),
        str(decision.get("rationale") or "").strip(),
        tuple(_clean_string_list(decision.get("alternatives"), limit=8)),
        tuple(_clean_string_list(decision.get("constraints"), limit=8)),
        tuple(_clean_string_list(decision.get("risks"), limit=8)),
        tuple(_clean_string_list(decision.get("related_paths"), limit=8)),
        str(decision.get("subsystem") or "").strip(),
    )


def _dedupe_exact_rows(rows: list[dict[str, Any]], *, signature_fn: Any) -> tuple[list[dict[str, Any]], int]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    removed = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        signature = signature_fn(row)
        if signature in seen:
            removed += 1
            continue
        seen.add(signature)
        deduped.append(row)
    return deduped, removed


def _failure_signature_value(row: dict[str, Any]) -> str:
    return str(row.get("failure_signature") or row.get("signature") or "").strip()


def _merge_failure_group(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = [dict(row) for row in rows if isinstance(row, dict)]
    ordered.sort(key=lambda row: str(row.get("timestamp") or ""))
    base = ordered[0] if ordered else {}
    merged = dict(base)
    merged["symptoms"] = _merge_unique(*(row.get("symptoms") for row in ordered), limit=8)  # type: ignore[arg-type]
    merged["failed_attempts"] = _merge_unique(*(row.get("failed_attempts") for row in ordered), limit=8)  # type: ignore[arg-type]
    merged["ineffective_commands"] = _merge_unique(*(row.get("ineffective_commands") for row in ordered), limit=8)  # type: ignore[arg-type]
    merged["related_paths"] = _merge_unique(*(row.get("related_paths") for row in ordered), limit=12)  # type: ignore[arg-type]
    merged["files_involved"] = _merge_unique(*(row.get("files_involved") for row in ordered), limit=12)  # type: ignore[arg-type]
    merged["occurrences"] = sum(int(row.get("occurrences", 1) or 1) for row in ordered)
    latest = max(ordered, key=lambda row: str(row.get("timestamp") or ""))
    merged["timestamp"] = str(latest.get("timestamp") or merged.get("timestamp") or "")
    merged["last_execution_id"] = str(latest.get("last_execution_id") or merged.get("last_execution_id") or "")
    if any(str(row.get("status") or "") == "resolved" for row in ordered):
        resolved = max(
            (row for row in ordered if str(row.get("status") or "") == "resolved"),
            key=lambda row: str(row.get("timestamp") or ""),
        )
        merged["status"] = "resolved"
        merged["resolved_by_execution_id"] = str(resolved.get("resolved_by_execution_id") or resolved.get("resolved_by") or "")
        merged["resolved_by"] = str(resolved.get("resolved_by") or resolved.get("resolved_by_execution_id") or "")
    return merged


def _merge_unique(*value_groups: Any, limit: int = 12) -> list[str]:
    combined: list[str] = []
    for group in value_groups:
        combined.extend(_clean_string_list(group, limit=limit))
    return _clean_string_list(combined, limit=limit)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_iso(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _age_days(value: Any, *, now: datetime) -> int | None:
    timestamp = _parse_iso(value)
    if not timestamp:
        return None
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return max(0, int((now - timestamp).total_seconds() // 86400))


def _path_exists(repo_root: Path, relative_path: str) -> bool:
    path = str(relative_path or "").strip()
    if not path:
        return False
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate.exists()
    return (repo_root / candidate).exists()


def _missing_paths(repo_root: Path, paths: Any) -> list[str]:
    return [path for path in _clean_string_list(paths, limit=16) if not _path_exists(repo_root, path)]


def _decision_ref(decision: dict[str, Any], index: int) -> str:
    execution_id = str(decision.get("execution_id") or "").strip()
    decision_text = str(decision.get("decision") or "").strip()
    return f"{execution_id}:{decision_text}" if execution_id or decision_text else f"index:{index}"


def _stale_decision_refs(staleness: dict[str, Any]) -> set[str]:
    rows = staleness.get("decisions") if isinstance(staleness.get("decisions"), list) else []
    return {str(row.get("ref") or "") for row in rows if isinstance(row, dict) and bool(row.get("stale"))}


def _stale_strategy_ids(staleness: dict[str, Any]) -> list[str]:
    rows = staleness.get("strategies") if isinstance(staleness.get("strategies"), list) else []
    return [str(row.get("task_id") or "") for row in rows if isinstance(row, dict) and bool(row.get("stale")) and str(row.get("task_id") or "").strip()]


def _stale_subsystem_names(staleness: dict[str, Any]) -> set[str]:
    semantic = staleness.get("semantic_repo") if isinstance(staleness.get("semantic_repo"), dict) else {}
    rows = semantic.get("subsystems") if isinstance(semantic.get("subsystems"), list) else []
    return {str(row.get("name") or "") for row in rows if isinstance(row, dict) and bool(row.get("stale"))}


def _handoff_is_stale(staleness: dict[str, Any]) -> bool:
    handoff = staleness.get("handoff") if isinstance(staleness.get("handoff"), dict) else {}
    return bool(handoff.get("stale"))


def _observed_files(prepared: dict[str, Any]) -> list[str]:
    log = prepared.get("last_execution_log") if isinstance(prepared.get("last_execution_log"), dict) else {}
    observation = prepared.get("execution_observation") if isinstance(prepared.get("execution_observation"), dict) else {}
    candidates: list[str] = []
    for source in (log, observation):
        for key in ("files_edited", "files_opened"):
            value = source.get(key)
            if isinstance(value, list):
                candidates.extend(str(item) for item in value)
    return _clean_string_list(candidates, limit=8)


def _has_nonempty_list(payload: dict[str, Any], key: str) -> bool:
    value = payload.get(key)
    return isinstance(value, list) and any(str(item or "").strip() for item in value)


def is_nontrivial_handoff_candidate(
    prepared: dict[str, Any],
    result: dict[str, Any],
    *,
    strategy_stored: bool = False,
    failure_recorded: bool = False,
    learning_stored: bool = False,
) -> bool:
    log = prepared.get("last_execution_log") if isinstance(prepared.get("last_execution_log"), dict) else {}
    observation = prepared.get("execution_observation") if isinstance(prepared.get("execution_observation"), dict) else {}
    for payload in (log, observation):
        if any(_has_nonempty_list(payload, key) for key in ("files_edited", "commands_executed", "tests_executed", "notable_errors")):
            return True
    if strategy_stored or failure_recorded or learning_stored:
        return True
    summary = str(result.get("result_summary") or "").strip()
    return bool(summary)


def persist_handoff_memory(
    repo_root: Path,
    prepared: dict[str, Any],
    result: dict[str, Any],
    *,
    timestamp: str,
    strategy_stored: bool = False,
    failure_recorded: bool = False,
    learning_stored: bool = False,
) -> dict[str, Any] | None:
    if not is_nontrivial_handoff_candidate(
        prepared,
        result,
        strategy_stored=strategy_stored,
        failure_recorded=failure_recorded,
        learning_stored=learning_stored,
    ):
        return None
    handoff_payload = result.get("handoff") if isinstance(result.get("handoff"), dict) else {}
    summary = str(handoff_payload.get("summary") or result.get("result_summary") or "").strip()
    if not summary:
        return None
    session = prepared.get("continuity_context", {}).get("session", {}) if isinstance(prepared.get("continuity_context"), dict) else {}
    try:
        source_session = int(session.get("session_count") or 0) if isinstance(session, dict) else 0
    except (TypeError, ValueError):
        source_session = 0
    source_execution_id = str(prepared.get("envelope", {}).get("execution_id") or "") if isinstance(prepared.get("envelope"), dict) else ""
    tests_observed = _clean_string_list(
        list(prepared.get("last_execution_log", {}).get("tests_executed", []))
        if isinstance(prepared.get("last_execution_log"), dict) and isinstance(prepared.get("last_execution_log", {}).get("tests_executed"), list)
        else [],
        limit=8,
    )
    status = "resolved" if bool(result.get("success")) else ("failed" if failure_recorded else "unresolved")
    task_type = str(prepared.get("effective_task_type") or prepared.get("resolved_task_type") or "")
    reason = str(prepared.get("envelope", {}).get("user_request") or "") if isinstance(prepared.get("envelope"), dict) else ""
    files_observed = len(_observed_files(prepared))
    completed = _clean_string_list(handoff_payload.get("completed"), limit=8) or [summary]
    next_steps = _clean_string_list(handoff_payload.get("next_steps"), limit=8)
    blocked = _clean_string_list(handoff_payload.get("blocked") or handoff_payload.get("open_items"), limit=8)
    risks = _clean_string_list(handoff_payload.get("risks"), limit=8)
    recommended = _clean_string_list(handoff_payload.get("recommended_starting_points"), limit=8) or _observed_files(prepared)
    handoff = {
        "summary": summary,
        "completed": completed,
        "next_steps": next_steps,
        "blocked": blocked,
        "open_items": blocked,
        "risks": risks,
        "recommended_starting_points": recommended,
        "updated_at": timestamp,
        "source_session": source_session,
        "source_execution_id": source_execution_id,
    }
    write_json(repo_root / HANDOFF_PATH, handoff)
    history = append_handoff_history(
        repo_root,
        {
            "execution_id": source_execution_id,
            "timestamp": timestamp,
            "summary": summary,
            "completed": completed,
            "next_steps": next_steps,
            "blocked": blocked,
            "risks": risks,
            "status": status,
            "reason": reason,
            "task_type": task_type,
            "recommended_starting_points": handoff.get("recommended_starting_points", []),
            "files_observed": files_observed,
            "tests_observed": tests_observed,
        },
        limit=10,
    )
    return {"path": (repo_root / HANDOFF_PATH).as_posix(), "handoff": handoff, "history": history}


def _significant_decision(decision: dict[str, Any]) -> bool:
    if not str(decision.get("decision") or "").strip():
        return False
    if str(decision.get("rationale") or "").strip():
        return True
    return any(_clean_string_list(decision.get(key), limit=1) for key in ("alternatives", "constraints", "risks", "related_paths"))


def _session_count_from_prepared(prepared: dict[str, Any]) -> int:
    session = prepared.get("continuity_context", {}).get("session", {}) if isinstance(prepared.get("continuity_context"), dict) else {}
    try:
        return int(session.get("session_count") or 0) if isinstance(session, dict) else 0
    except (TypeError, ValueError):
        return 0


def persist_decision_memory(
    repo_root: Path,
    prepared: dict[str, Any],
    result: dict[str, Any],
    *,
    timestamp: str,
) -> list[dict[str, Any]]:
    raw_decisions = result.get("decisions")
    if not isinstance(raw_decisions, list):
        return []
    session_count = _session_count_from_prepared(prepared)
    execution_id = str(prepared.get("envelope", {}).get("execution_id") or "") if isinstance(prepared.get("envelope"), dict) else ""
    persisted: list[dict[str, Any]] = []
    for raw in raw_decisions:
        if not isinstance(raw, dict):
            continue
        if not _significant_decision(raw):
            continue
        entry = {
            "decision": str(raw.get("decision") or "").strip(),
            "rationale": str(raw.get("rationale") or "").strip(),
            "alternatives": _clean_string_list(raw.get("alternatives"), limit=8),
            "constraints": _clean_string_list(raw.get("constraints"), limit=8),
            "risks": _clean_string_list(raw.get("risks"), limit=8),
            "related_paths": _clean_string_list(raw.get("related_paths"), limit=8),
            "subsystem": str(raw.get("subsystem") or "").strip(),
            "timestamp": timestamp,
            "session": session_count,
            "execution_id": execution_id,
        }
        append_jsonl(repo_root / DECISIONS_PATH, entry)
        persisted.append(entry)
    return persisted


def _normalize_subsystem_update(raw: dict[str, Any], observed_files: list[str], observed_tests: list[str]) -> dict[str, Any] | None:
    name = str(raw.get("name") or "").strip()
    if not name:
        return None
    key_paths = _merge_unique(raw.get("key_paths"), observed_files)
    relevant_tests = _merge_unique(raw.get("relevant_tests"), observed_tests)
    return {
        "name": name,
        "description": str(raw.get("description") or "").strip(),
        "key_paths": key_paths,
        "entry_points": _clean_string_list(raw.get("entry_points"), limit=8),
        "relevant_tests": relevant_tests,
        "fragile_areas": _clean_string_list(raw.get("fragile_areas"), limit=8),
    }


def _semantic_session(prepared: dict[str, Any]) -> int:
    session = prepared.get("continuity_context", {}).get("session", {}) if isinstance(prepared.get("continuity_context"), dict) else {}
    try:
        return int(session.get("session_count") or 0) if isinstance(session, dict) else 0
    except (TypeError, ValueError):
        return 0


def persist_semantic_repo_memory(
    repo_root: Path,
    prepared: dict[str, Any],
    result: dict[str, Any],
    *,
    timestamp: str,
) -> dict[str, Any] | None:
    raw_updates = result.get("semantic_repo")
    if not isinstance(raw_updates, list):
        return None
    observation = prepared.get("execution_observation") if isinstance(prepared.get("execution_observation"), dict) else {}
    observed_files = _clean_string_list(
        list(observation.get("files_edited", []) or []) + list(observation.get("files_opened", []) or []),
        limit=12,
    )
    observed_tests = _clean_string_list(observation.get("tests_executed", []), limit=12)
    updates = [item for item in (_normalize_subsystem_update(raw, observed_files, observed_tests) for raw in raw_updates if isinstance(raw, dict)) if item]
    if not updates:
        return None
    path = repo_root / SEMANTIC_REPO_PATH
    existing = read_json(path, {})
    if not isinstance(existing, dict):
        existing = {}
    existing_subsystems = existing.get("subsystems") if isinstance(existing.get("subsystems"), list) else []
    by_name: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for raw in existing_subsystems:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name") or "").strip()
        if not name:
            continue
        by_name[name] = {
            "name": name,
            "description": str(raw.get("description") or "").strip(),
            "key_paths": _clean_string_list(raw.get("key_paths"), limit=12),
            "entry_points": _clean_string_list(raw.get("entry_points"), limit=8),
            "relevant_tests": _clean_string_list(raw.get("relevant_tests"), limit=12),
            "fragile_areas": _clean_string_list(raw.get("fragile_areas"), limit=8),
        }
        order.append(name)
    for update in updates:
        name = update["name"]
        current = by_name.get(name)
        if current:
            current["description"] = update["description"] or current.get("description", "")
            current["key_paths"] = _merge_unique(current.get("key_paths"), update.get("key_paths"), limit=12)
            current["entry_points"] = _merge_unique(current.get("entry_points"), update.get("entry_points"), limit=8)
            current["relevant_tests"] = _merge_unique(current.get("relevant_tests"), update.get("relevant_tests"), limit=12)
            current["fragile_areas"] = _merge_unique(current.get("fragile_areas"), update.get("fragile_areas"), limit=8)
        else:
            by_name[name] = update
            order.append(name)
    payload = {
        "repo_id": str(existing.get("repo_id") or repo_root.name),
        "subsystems": [by_name[name] for name in order if name in by_name],
        "updated_at": timestamp,
        "source_session": _semantic_session(prepared),
    }
    write_json(path, payload)
    return {"path": path.as_posix(), "subsystems_updated": [item["name"] for item in updates], "semantic_repo": payload}


def _write_jsonl_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + ("\n" if rows else ""),
        encoding="utf-8",
    )


def maintain_continuity_hygiene(repo_root: Path) -> dict[str, Any]:
    report = {
        "handoff": {"canonical": True, "duplicates_removed": 0},
        "decisions": {"before": 0, "after": 0, "duplicates_removed": 0},
        "failure_patterns": {"before": 0, "after": 0, "merged_groups": 0, "duplicates_removed": 0},
        "semantic_repo": {"subsystems_touched": 0, "strings_deduped": 0},
    }

    decisions = read_jsonl(repo_root / DECISIONS_PATH)
    deduped_decisions, removed_decisions = _dedupe_exact_rows(decisions, signature_fn=_decision_signature)
    report["decisions"] = {
        "before": len(decisions),
        "after": len(deduped_decisions),
        "duplicates_removed": removed_decisions,
    }
    if removed_decisions:
        _write_jsonl_rows(repo_root / DECISIONS_PATH, deduped_decisions)

    failures = read_jsonl(repo_root / FAILURE_PATTERNS_PATH)
    grouped_failures: dict[str, list[dict[str, Any]]] = {}
    ordered_signatures: list[str] = []
    passthrough_failures: list[dict[str, Any]] = []
    for row in failures:
        signature = _failure_signature_value(row)
        if not signature:
            passthrough_failures.append(row)
            continue
        if signature not in grouped_failures:
            grouped_failures[signature] = []
            ordered_signatures.append(signature)
        grouped_failures[signature].append(row)
    merged_failures = list(passthrough_failures)
    merged_groups = 0
    duplicates_removed = 0
    for signature in ordered_signatures:
        group = grouped_failures[signature]
        if len(group) == 1:
            merged_failures.append(group[0])
            continue
        merged_failures.append(_merge_failure_group(group))
        merged_groups += 1
        duplicates_removed += len(group) - 1
    report["failure_patterns"] = {
        "before": len(failures),
        "after": len(merged_failures),
        "merged_groups": merged_groups,
        "duplicates_removed": duplicates_removed,
    }
    if merged_groups:
        _write_jsonl_rows(repo_root / FAILURE_PATTERNS_PATH, merged_failures)

    semantic_path = repo_root / SEMANTIC_REPO_PATH
    semantic_payload = read_json(semantic_path, {})
    if isinstance(semantic_payload, dict) and isinstance(semantic_payload.get("subsystems"), list):
        touched = 0
        strings_deduped = 0
        normalized_subsystems: list[dict[str, Any]] = []
        for raw in semantic_payload.get("subsystems", []):
            if not isinstance(raw, dict):
                continue
            before_counts = {
                "key_paths": len(raw.get("key_paths", [])) if isinstance(raw.get("key_paths"), list) else 0,
                "entry_points": len(raw.get("entry_points", [])) if isinstance(raw.get("entry_points"), list) else 0,
                "relevant_tests": len(raw.get("relevant_tests", [])) if isinstance(raw.get("relevant_tests"), list) else 0,
                "fragile_areas": len(raw.get("fragile_areas", [])) if isinstance(raw.get("fragile_areas"), list) else 0,
            }
            normalized = {
                "name": str(raw.get("name") or "").strip(),
                "description": str(raw.get("description") or "").strip(),
                "key_paths": _clean_string_list(raw.get("key_paths"), limit=12),
                "entry_points": _clean_string_list(raw.get("entry_points"), limit=8),
                "relevant_tests": _clean_string_list(raw.get("relevant_tests"), limit=12),
                "fragile_areas": _clean_string_list(raw.get("fragile_areas"), limit=8),
            }
            after_counts = {
                "key_paths": len(normalized["key_paths"]),
                "entry_points": len(normalized["entry_points"]),
                "relevant_tests": len(normalized["relevant_tests"]),
                "fragile_areas": len(normalized["fragile_areas"]),
            }
            removed_here = sum(before_counts[key] - after_counts[key] for key in before_counts)
            if removed_here:
                touched += 1
                strings_deduped += removed_here
            normalized_subsystems.append(normalized)
        if strings_deduped:
            semantic_payload = dict(semantic_payload)
            semantic_payload["subsystems"] = normalized_subsystems
            write_json(semantic_path, semantic_payload)
        report["semantic_repo"] = {
            "subsystems_touched": touched,
            "strings_deduped": strings_deduped,
        }

    write_json(repo_root / DEDUPE_REPORT_PATH, report)
    return {"path": (repo_root / DEDUPE_REPORT_PATH).as_posix(), "report": report}


def refresh_staleness(
    repo_root: Path,
    *,
    now: datetime | None = None,
    handoff_max_age_days: int = 14,
    subsystem_max_age_days: int = 60,
    persist: bool = True,
) -> dict[str, Any]:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    report: dict[str, Any] = {
        "updated_at": current.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "handoff": {"stale": False, "reasons": []},
        "decisions": [],
        "semantic_repo": {"subsystems": []},
        "strategies": [],
    }

    handoff = read_json(repo_root / HANDOFF_PATH, {})
    if isinstance(handoff, dict) and handoff:
        reasons: list[str] = []
        missing = _missing_paths(repo_root, handoff.get("recommended_starting_points"))
        if missing:
            reasons.append("missing_paths:" + ",".join(missing[:5]))
        age = _age_days(handoff.get("updated_at"), now=current)
        if age is not None and age > handoff_max_age_days:
            reasons.append(f"age_days:{age}")
        report["handoff"] = {"stale": bool(reasons), "reasons": reasons}

    decisions = read_jsonl(repo_root / DECISIONS_PATH)
    latest_by_subsystem: dict[str, tuple[int, dict[str, Any]]] = {}
    for index, decision in enumerate(decisions):
        subsystem = str(decision.get("subsystem") or "").strip()
        if not subsystem:
            continue
        latest_by_subsystem[subsystem] = (index, decision)
    decision_rows: list[dict[str, Any]] = []
    for index, decision in enumerate(decisions):
        reasons = []
        missing = _missing_paths(repo_root, decision.get("related_paths"))
        if missing:
            reasons.append("missing_paths:" + ",".join(missing[:5]))
        subsystem = str(decision.get("subsystem") or "").strip()
        latest = latest_by_subsystem.get(subsystem) if subsystem else None
        if latest and latest[0] > index:
            reasons.append(f"superseded_by:{_decision_ref(latest[1], latest[0])}")
        if reasons:
            decision_rows.append({
                "ref": _decision_ref(decision, index),
                "execution_id": str(decision.get("execution_id") or ""),
                "subsystem": subsystem,
                "stale": True,
                "reasons": reasons,
            })
    report["decisions"] = decision_rows

    semantic = read_json(repo_root / SEMANTIC_REPO_PATH, {})
    if isinstance(semantic, dict) and isinstance(semantic.get("subsystems"), list):
        subsystem_rows: list[dict[str, Any]] = []
        for subsystem in semantic.get("subsystems", []):
            if not isinstance(subsystem, dict):
                continue
            name = str(subsystem.get("name") or "").strip()
            reasons = []
            key_paths = _clean_string_list(subsystem.get("key_paths"), limit=12)
            missing = _missing_paths(repo_root, key_paths)
            if key_paths and len(missing) == len(key_paths):
                reasons.append("all_key_paths_missing:" + ",".join(missing[:5]))
            age = _age_days(semantic.get("updated_at"), now=current)
            if age is not None and age > subsystem_max_age_days:
                reasons.append(f"not_observed_days:{age}")
            if reasons:
                subsystem_rows.append({"name": name, "stale": True, "reasons": reasons})
        report["semantic_repo"] = {"subsystems": subsystem_rows}

    strategy_rows: list[dict[str, Any]] = []
    for strategy in load_strategies(repo_root):
        task_id = str(strategy.get("task_id") or "").strip()
        paths = _clean_string_list(
            list(strategy.get("files_used", []) or []) + list(strategy.get("entry_points", []) or []),
            limit=16,
        )
        missing = _missing_paths(repo_root, paths)
        if task_id and paths and len(missing) == len(paths):
            strategy_rows.append({"task_id": task_id, "stale": True, "reasons": ["all_paths_missing:" + ",".join(missing[:5])]})
    report["strategies"] = strategy_rows

    if persist:
        write_json(repo_root / STALENESS_PATH, report)
    return {"path": (repo_root / STALENESS_PATH).as_posix(), "staleness": report}


def update_continuity_metrics(
    repo_root: Path,
    prepared: dict[str, Any],
    telemetry_entry: dict[str, Any],
) -> dict[str, Any]:
    existing = read_json(repo_root / CONTINUITY_METRICS_PATH, {})
    if not isinstance(existing, dict):
        existing = {}
    continuity = prepared.get("continuity_context", {}) if isinstance(prepared.get("continuity_context"), dict) else {}
    loaded = continuity.get("loaded", {}) if isinstance(continuity.get("loaded"), dict) else {}
    reuse = continuity.get("procedural_reuse", {}) if isinstance(continuity.get("procedural_reuse"), dict) else {}
    cross_memory = reuse.get("cross_memory_reuse", {}) if isinstance(reuse.get("cross_memory_reuse"), dict) else {}
    payload = {
        "strategy_reuse_count": int(existing.get("strategy_reuse_count", 0) or 0),
        "non_reuse_count": int(existing.get("non_reuse_count", 0) or 0),
        "handoff_load_count": int(existing.get("handoff_load_count", 0) or 0),
        "decision_load_count": int(existing.get("decision_load_count", 0) or 0),
        "failure_match_count": int(existing.get("failure_match_count", 0) or 0),
        "semantic_memory_load_count": int(existing.get("semantic_memory_load_count", 0) or 0),
        "repeated_failure_avoidance_count": int(existing.get("repeated_failure_avoidance_count", 0) or 0),
    }
    if bool(telemetry_entry.get("used_strategy")):
        payload["strategy_reuse_count"] += 1
    else:
        payload["non_reuse_count"] += 1
    if bool(loaded.get("handoff")):
        payload["handoff_load_count"] += 1
    if bool(loaded.get("decisions")):
        payload["decision_load_count"] += 1
    if bool(loaded.get("failures")):
        payload["failure_match_count"] += 1
    if bool(loaded.get("semantic_repo")):
        payload["semantic_memory_load_count"] += 1
    if bool(cross_memory.get("known_failure_avoidance")) or (bool(loaded.get("failures")) and bool(telemetry_entry.get("success"))):
        payload["repeated_failure_avoidance_count"] += 1
    payload["updated_at"] = _now_iso()
    write_json(repo_root / CONTINUITY_METRICS_PATH, payload)
    return {"path": (repo_root / CONTINUITY_METRICS_PATH).as_posix(), "metrics": payload}


def _load_semantic_repo(
    repo_root: Path,
    warnings: list[str],
    *,
    request_text: str,
    files: list[str],
    area_id: str,
    stale_subsystems: set[str] | None = None,
    max_full_subsystems: int = 4,
    max_relevant_subsystems: int = 3,
) -> dict[str, Any]:
    payload = _read_optional_json(repo_root, SEMANTIC_REPO_PATH, dict, warnings)
    if not payload:
        return {}
    subsystems = payload.get("subsystems") if isinstance(payload.get("subsystems"), list) else []
    normalized: list[dict[str, Any]] = []
    stale_names = stale_subsystems or set()
    for raw in subsystems:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name") or "").strip()
        if not name:
            continue
        if name in stale_names:
            continue
        normalized.append({
            "name": name,
            "description": str(raw.get("description") or "").strip(),
            "key_paths": _clean_string_list(raw.get("key_paths"), limit=12),
            "entry_points": _clean_string_list(raw.get("entry_points"), limit=8),
            "relevant_tests": _clean_string_list(raw.get("relevant_tests"), limit=12),
            "fragile_areas": _clean_string_list(raw.get("fragile_areas"), limit=8),
        })
    compact = len(normalized) <= max_full_subsystems
    if compact:
        return {
            "repo_id": str(payload.get("repo_id") or repo_root.name),
            "subsystems": normalized,
            "updated_at": str(payload.get("updated_at") or ""),
            "source_session": payload.get("source_session"),
        }
    tokens = {token for token in str(request_text or "").lower().replace("/", " ").replace("_", " ").split() if len(token) > 2}
    file_set = set(files or [])
    ranked: list[tuple[int, dict[str, Any]]] = []
    for subsystem in normalized:
        score = 0
        name = subsystem["name"].lower()
        description = subsystem["description"].lower()
        score += len(tokens.intersection(set(name.replace("_", " ").split()))) * 3
        score += len(tokens.intersection(set(description.replace("_", " ").split())))
        key_paths = subsystem.get("key_paths", []) if isinstance(subsystem.get("key_paths"), list) else []
        if file_set.intersection(set(key_paths)):
            score += 4
        if area_id and any(str(path).startswith(area_id) for path in key_paths):
            score += 3
        entry_points = subsystem.get("entry_points", []) if isinstance(subsystem.get("entry_points"), list) else []
        score += len(tokens.intersection(set(" ".join(entry_points).lower().replace("_", " ").split())))
        if score > 0:
            ranked.append((score, subsystem))
    ranked.sort(key=lambda item: (-item[0], item[1]["name"]))
    selected = [subsystem for _, subsystem in ranked[:max_relevant_subsystems]]
    return {
        "repo_id": str(payload.get("repo_id") or repo_root.name),
        "subsystems": selected,
        "updated_at": str(payload.get("updated_at") or ""),
        "source_session": payload.get("source_session"),
    }


def _strategy_paths(strategy: dict[str, Any]) -> list[str]:
    return _clean_string_list(
        list(strategy.get("files_used", []) or [])
        + list(strategy.get("entry_points", []) or [])
        + list(strategy.get("files_edited", []) or []),
        limit=16,
    )


def _continuity_reuse_files(
    *,
    files: list[str],
    handoff: dict[str, Any],
    decisions: list[dict[str, Any]],
    semantic_repo: dict[str, Any],
) -> list[str]:
    candidates: list[str] = list(files)
    candidates.extend(_clean_string_list(handoff.get("recommended_starting_points"), limit=8))
    for decision in decisions:
        candidates.extend(_clean_string_list(decision.get("related_paths"), limit=6))
    for subsystem in semantic_repo.get("subsystems", []) if isinstance(semantic_repo.get("subsystems"), list) else []:
        if not isinstance(subsystem, dict):
            continue
        candidates.extend(_clean_string_list(subsystem.get("key_paths"), limit=6))
        candidates.extend(_clean_string_list(subsystem.get("entry_points"), limit=4))
    return _clean_string_list(candidates, limit=20)


def _request_tokens(text: str) -> set[str]:
    return {token for token in str(text or "").lower().replace("/", " ").replace("_", " ").replace("-", " ").split() if len(token) > 2}


def _live_paths(repo_root: Path, paths: Any, *, limit: int = 8) -> list[str]:
    return [path for path in _clean_string_list(paths, limit=limit) if _path_exists(repo_root, path)]


def _rank_text_score(tokens: set[str], *texts: Any) -> int:
    if not tokens:
        return 0
    haystack = " ".join(str(text or "").lower().replace("_", " ") for text in texts)
    return min(20, len(tokens.intersection(set(haystack.split()))) * 4)


def _ranked_item(
    *,
    kind: str,
    item_id: str,
    title: str,
    score: int,
    reasons: list[str],
    paths: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "kind": kind,
        "id": item_id,
        "title": title[:160],
        "score": int(score),
        "reasons": _clean_string_list(reasons, limit=8),
        "paths": _clean_string_list(paths or [], limit=8),
        "metadata": metadata or {},
    }


def build_ranked_continuity_items(
    repo_root: Path,
    *,
    request_text: str,
    files: list[str],
    handoff: dict[str, Any],
    decisions: list[dict[str, Any]],
    failures: list[dict[str, Any]],
    semantic_repo: dict[str, Any],
    procedural_reuse: dict[str, Any],
    staleness: dict[str, Any],
) -> list[dict[str, Any]]:
    tokens = _request_tokens(request_text)
    target_files = set(_clean_string_list(files, limit=20))
    items: list[dict[str, Any]] = []

    items.extend(_repo_map_ranked_items(repo_root, request_text=request_text, files=list(files or [])))

    if handoff:
        paths = _clean_string_list(handoff.get("recommended_starting_points"), limit=8)
        live = _live_paths(repo_root, paths, limit=8)
        score = 35 + len(set(live).intersection(target_files)) * 20 + len(live) * 3
        reasons = ["handoff_loaded"]
        if live:
            reasons.append("live_starting_points")
        if _handoff_is_stale(staleness):
            score -= 40
            reasons.append("stale_penalty")
        items.append(_ranked_item(
            kind="handoff",
            item_id=str(handoff.get("source_execution_id") or "handoff"),
            title=str(handoff.get("summary") or "handoff"),
            score=score,
            reasons=reasons,
            paths=live or paths,
        ))

    for index, decision in enumerate(decisions):
        paths = _clean_string_list(decision.get("related_paths"), limit=8)
        live = _live_paths(repo_root, paths, limit=8)
        score = 25 + _rank_text_score(tokens, decision.get("decision"), decision.get("rationale"), decision.get("subsystem"))
        if live:
            score += 10 + len(set(live).intersection(target_files)) * 20
        if paths and not live:
            score -= 15
        reasons = ["recent_decision"]
        if live:
            reasons.append("live_related_paths")
        items.append(_ranked_item(
            kind="decision",
            item_id=_decision_ref(decision, index),
            title=str(decision.get("decision") or "decision"),
            score=score,
            reasons=reasons,
            paths=live or paths,
            metadata={"subsystem": str(decision.get("subsystem") or "")},
        ))

    for index, failure in enumerate(failures):
        paths = _clean_string_list(list(failure.get("related_paths", []) or []) + list(failure.get("files_involved", []) or []), limit=8)
        live = _live_paths(repo_root, paths, limit=8)
        score = 30 + _rank_text_score(tokens, failure.get("signature"), failure.get("failure_signature"), failure.get("error_text"))
        if live:
            score += 8
        reasons = ["relevant_failure"]
        if live:
            reasons.append("live_failure_paths")
        items.append(_ranked_item(
            kind="failure",
            item_id=str(failure.get("failure_id") or failure.get("signature") or f"failure:{index}"),
            title=str(failure.get("signature") or failure.get("failure_signature") or "failure"),
            score=score,
            reasons=reasons,
            paths=live or paths,
        ))

    for subsystem in semantic_repo.get("subsystems", []) if isinstance(semantic_repo.get("subsystems"), list) else []:
        if not isinstance(subsystem, dict):
            continue
        paths = _clean_string_list(subsystem.get("key_paths"), limit=8)
        live = _live_paths(repo_root, paths, limit=8)
        score = 20 + _rank_text_score(tokens, subsystem.get("name"), subsystem.get("description"), " ".join(subsystem.get("entry_points", []) or []))
        if live:
            score += 8 + len(set(live).intersection(target_files)) * 20
        if paths and not live:
            score -= 20
        reasons = ["semantic_repo_match"]
        if live:
            reasons.append("live_key_paths")
        items.append(_ranked_item(
            kind="semantic_repo",
            item_id=str(subsystem.get("name") or "subsystem"),
            title=str(subsystem.get("name") or "subsystem"),
            score=score,
            reasons=reasons,
            paths=live or paths,
            metadata={"entry_points": _clean_string_list(subsystem.get("entry_points"), limit=4)},
        ))

    if procedural_reuse:
        paths = _strategy_paths(procedural_reuse)
        live = _live_paths(repo_root, paths, limit=8)
        confidence = strategy_reuse_confidence(procedural_reuse)
        base = {"high": 50, "medium": 35, "low": 20}.get(confidence, 20)
        score = base + int(procedural_reuse.get("score", 0) or 0) // 100
        reasons = ["procedural_reuse", f"confidence:{confidence}"]
        if live:
            reasons.append("live_strategy_paths")
        items.append(_ranked_item(
            kind="strategy",
            item_id=str(procedural_reuse.get("task_id") or "strategy"),
            title=str(procedural_reuse.get("task_text") or procedural_reuse.get("selection_reason") or "strategy"),
            score=score,
            reasons=reasons,
            paths=live or paths,
            metadata={
                "reuse_confidence": confidence,
                "selection_reason": str(procedural_reuse.get("selection_reason") or ""),
            },
        ))

    return _bounded_ranked_items(items, limit=12, repo_map_limit=3)


def _repo_map_ranked_items(repo_root: Path, *, request_text: str, files: list[str]) -> list[dict[str, Any]]:
    if not str(request_text or "").strip() and not _clean_string_list(files, limit=20):
        return []
    try:
        from .repo_map.config import load_repomap_config
        from .repo_map.query import query_repo_map

        config = load_repomap_config(repo_root)
        if not bool(config.get("enabled", False)):
            return []
        active_files = _clean_string_list(files, limit=20)
        query_text = str(request_text or "").strip() or " ".join(active_files)
        raw_items = query_repo_map(repo_root, query_text, files=active_files, limit=8)
        return _continuity_repo_map_items(raw_items, active_files=active_files, limit=3)
    except Exception:
        return []


def _continuity_repo_map_items(items: list[dict[str, Any]], *, active_files: list[str], limit: int) -> list[dict[str, Any]]:
    if not items:
        return []
    strong_kinds = {"function", "class", "entrypoint"}
    weak_context_kinds = {"heading", "config_key", "file", "module", "import", "constant"}
    has_strong = any(
        str((item.get("metadata") if isinstance(item.get("metadata"), dict) else {}).get("symbol_kind") or "") in strong_kinds
        for item in items
        if isinstance(item, dict)
    )
    active = set(_clean_string_list(active_files, limit=20))
    filtered: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        symbol_kind = str(metadata.get("symbol_kind") or "")
        paths = _clean_string_list(item.get("paths"), limit=4)
        if has_strong and symbol_kind in weak_context_kinds and not active.intersection(paths):
            continue
        bounded = dict(item)
        original_score = int(bounded.get("score", 0) or 0)
        score_cap = 44 if active.intersection(paths) else 34
        bounded["score"] = min(original_score, score_cap)
        reasons = _clean_string_list(bounded.get("reasons"), limit=8)
        if original_score > bounded["score"] and "repo_map:continuity_capped" not in reasons:
            reasons.append("repo_map:continuity_capped")
        bounded["reasons"] = reasons
        filtered.append(bounded)
    filtered.sort(key=lambda item: (-int(item.get("score", 0)), str(item.get("id") or ""), str(item.get("path") or "")))
    return filtered[: max(0, int(limit))]


def _bounded_ranked_items(items: list[dict[str, Any]], *, limit: int, repo_map_limit: int) -> list[dict[str, Any]]:
    ranked = sorted(items, key=lambda item: (-int(item.get("score", 0)), str(item.get("kind") or ""), str(item.get("id") or "")))
    selected: list[dict[str, Any]] = []
    repo_map_count = 0
    for item in ranked:
        if str(item.get("kind") or "") == "repo_map":
            if repo_map_count >= repo_map_limit:
                continue
            repo_map_count += 1
        selected.append(item)
        if len(selected) >= limit:
            break
    return selected


def _why_loaded_from_items(
    *,
    loaded: dict[str, Any],
    ranked_items: list[dict[str, Any]],
    staleness: dict[str, Any],
) -> dict[str, list[str]]:
    by_kind: dict[str, list[str]] = {}
    for item in ranked_items:
        kind = str(item.get("kind") or "")
        reasons = item.get("reasons") if isinstance(item.get("reasons"), list) else []
        by_kind.setdefault(kind, [])
        for reason in reasons:
            text = str(reason or "").strip()
            if text and text not in by_kind[kind]:
                by_kind[kind].append(text)
    why = {
        "handoff": by_kind.get("handoff", ["not_loaded"] if not loaded.get("handoff") else ["handoff_loaded"]),
        "decisions": by_kind.get("decision", ["not_loaded"] if not loaded.get("decisions") else ["recent_decisions_loaded"]),
        "failures": by_kind.get("failure", ["not_loaded"] if not loaded.get("failures") else ["relevant_failures_loaded"]),
        "semantic_repo": by_kind.get("semantic_repo", ["not_loaded"] if not loaded.get("semantic_repo") else ["semantic_repo_loaded"]),
        "procedural_reuse": by_kind.get("strategy", ["not_loaded"] if not loaded.get("procedural_reuse") else ["strategy_loaded"]),
        "repo_map": by_kind.get("repo_map", ["not_loaded"] if not loaded.get("repo_map") else ["repo_map_loaded"]),
    }
    if _handoff_is_stale(staleness) and "stale_excluded" not in why["handoff"]:
        why["handoff"] = ["stale_excluded"]
    return why


def build_continuity_brief(
    *,
    ranked_items: list[dict[str, Any]],
    handoff: dict[str, Any],
    decisions: list[dict[str, Any]],
    failures: list[dict[str, Any]],
    semantic_repo: dict[str, Any],
    procedural_reuse: dict[str, Any],
    why_loaded: dict[str, list[str]],
    active_work_state: dict[str, Any] | None = None,
    recent_work_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    probable_paths: list[str] = []
    for item in ranked_items:
        probable_paths.extend(_clean_string_list(item.get("paths"), limit=4))
    probable_paths.extend(_clean_string_list(handoff.get("recommended_starting_points"), limit=6))
    commands = _clean_string_list(
        _clean_string_list(procedural_reuse.get("related_commands"), limit=5)
        + _clean_string_list(procedural_reuse.get("commands_executed"), limit=5),
        limit=5,
    )
    tests = _clean_string_list(
        _clean_string_list(procedural_reuse.get("related_tests"), limit=5)
        + _clean_string_list(procedural_reuse.get("tests_executed"), limit=5),
        limit=5,
    )
    risks: list[str] = []
    risks.extend(_clean_string_list(handoff.get("risks"), limit=4))
    for decision in decisions:
        risks.extend(_clean_string_list(decision.get("risks"), limit=2))
    for failure in failures:
        risks.append(str(failure.get("signature") or failure.get("failure_signature") or failure.get("failure_id") or "").strip())
    for subsystem in semantic_repo.get("subsystems", []) if isinstance(semantic_repo.get("subsystems"), list) else []:
        if isinstance(subsystem, dict):
            risks.extend(_clean_string_list(subsystem.get("fragile_areas"), limit=2))
    active_state = compact_work_state_for_prepare(active_work_state or {})
    recent_state = compact_work_state_for_prepare(recent_work_state or {}) if not active_state else {}
    where = _clean_string_list(handoff.get("next_steps"), limit=3) or _clean_string_list(handoff.get("recommended_starting_points"), limit=3)
    if active_state.get("next_action"):
        where = [str(active_state.get("next_action"))]
    elif active_state.get("active_files"):
        where = _clean_string_list(active_state.get("active_files"), limit=3)
    elif not where and recent_state.get("next_action"):
        where = [str(recent_state.get("next_action"))]
    elif not where and recent_state.get("active_files"):
        where = _clean_string_list(recent_state.get("active_files"), limit=3)
    if not where:
        where = _clean_string_list(probable_paths, limit=3)
    commands = _clean_string_list(
        _clean_string_list(active_state.get("recommended_commands"), limit=5)
        + _clean_string_list(recent_state.get("recommended_commands"), limit=3)
        + commands,
        limit=5,
    )
    return {
        "version": 2,
        "where_to_continue": where,
        "active_work_state": {
            key: value for key, value in {
                "task_id": active_state.get("task_id", ""),
                "goal": active_state.get("goal", ""),
                "current_hypothesis": active_state.get("current_hypothesis", ""),
                "next_action": active_state.get("next_action", ""),
                "recommended_commands": list(active_state.get("recommended_commands", [])),
            }.items() if value not in ("", [], None)
        },
        "recent_work_state": {
            key: value for key, value in {
                "task_id": recent_state.get("task_id", ""),
                "status": recent_state.get("status", ""),
                "goal": recent_state.get("goal", ""),
                "current_hypothesis": recent_state.get("current_hypothesis", ""),
                "next_action": recent_state.get("next_action", ""),
                "recommended_commands": list(recent_state.get("recommended_commands", [])),
            }.items() if value not in ("", [], None)
        },
        "active_decisions": _clean_string_list([row.get("decision") for row in decisions if isinstance(row, dict)], limit=5),
        "probable_paths": _clean_string_list(probable_paths, limit=8),
        "known_risks": _clean_string_list(risks, limit=8),
        "recommended_commands": commands,
        "recommended_tests": tests,
        "reuse_confidence": strategy_reuse_confidence(procedural_reuse),
        "top_ranked_items": ranked_items[:5],
        "why_loaded": why_loaded,
    }


def render_next_text(brief: dict[str, Any]) -> str:
    if not isinstance(brief, dict) or not brief:
        return "AICTX next\n\nNo actionable continuity context available."
    lines = ["AICTX next"]
    active_work_state = brief.get("active_work_state") if isinstance(brief.get("active_work_state"), dict) else {}
    recent_work_state = brief.get("recent_work_state") if isinstance(brief.get("recent_work_state"), dict) else {}
    where = _clean_string_list(brief.get("where_to_continue"), limit=3)
    paths = _clean_string_list(brief.get("probable_paths"), limit=5)
    decisions = _clean_string_list(brief.get("active_decisions"), limit=2)
    risks = _clean_string_list(brief.get("known_risks"), limit=2)
    commands = _clean_string_list(brief.get("recommended_commands"), limit=3)
    tests = _clean_string_list(brief.get("recommended_tests"), limit=3)
    confidence = str(brief.get("reuse_confidence") or "").strip()

    if active_work_state:
        lines.extend(["", "Active work:"])
        goal = str(active_work_state.get("goal") or active_work_state.get("task_id") or "").strip()
        hypothesis = str(active_work_state.get("current_hypothesis") or "").strip()
        next_action = str(active_work_state.get("next_action") or "").strip()
        if goal:
            lines.append(f"- Goal: {goal}")
        if hypothesis:
            lines.append(f"- Hypothesis: {hypothesis}")
        if next_action:
            lines.append(f"- Next: {next_action}")
        verify = _clean_string_list(active_work_state.get("recommended_commands"), limit=2)
        if verify:
            lines.extend([f"- Verify: {item}" for item in verify])
    elif recent_work_state:
        lines.extend(["", "Recent paused/blocked work:"])
        goal = str(recent_work_state.get("goal") or recent_work_state.get("task_id") or "").strip()
        status = str(recent_work_state.get("status") or "").strip()
        hypothesis = str(recent_work_state.get("current_hypothesis") or "").strip()
        next_action = str(recent_work_state.get("next_action") or "").strip()
        if goal:
            suffix = f" ({status})" if status else ""
            lines.append(f"- Goal: {goal}{suffix}")
        if hypothesis:
            lines.append(f"- Hypothesis: {hypothesis}")
        if next_action:
            lines.append(f"- Next: {next_action}")
    if where:
        lines.extend(["", "Continue:"])
        lines.extend([f"- {item}" for item in where])
    elif paths:
        lines.extend(["", "Continue:"])
        lines.extend([f"- {item}" for item in paths[:3]])

    why_loaded = brief.get("why_loaded") if isinstance(brief.get("why_loaded"), dict) else {}
    why_lines: list[str] = []
    for source in ("handoff", "decisions", "semantic_repo", "procedural_reuse", "failures", "repo_map"):
        reasons = _clean_string_list(why_loaded.get(source), limit=2)
        reasons = [reason for reason in reasons if reason != "not_loaded"]
        if reasons:
            why_lines.append(f"{source}: {', '.join(reasons)}")
    if confidence:
        why_lines.append(f"reuse confidence: {confidence}")
    if why_lines:
        lines.extend(["", "Why:"])
        lines.extend([f"- {item}" for item in why_lines[:5]])

    if paths:
        lines.extend(["", "Paths:"])
        lines.extend([f"- {item}" for item in paths])

    if decisions:
        lines.extend(["", "Decisions:"])
        lines.extend([f"- {item}" for item in decisions])
    if risks:
        lines.extend(["", "Risks:"])
        lines.extend([f"- {item}" for item in risks])
    if commands or tests:
        lines.extend(["", "Run:"])
        lines.extend([f"- {item}" for item in _clean_string_list(commands + tests, limit=5)])
    return "\n".join(lines)


def _append_signal(strategy: dict[str, Any], signal: str) -> None:
    matched = strategy.get("matched_signals")
    if not isinstance(matched, list):
        matched = []
    if signal not in matched:
        matched.append(signal)
    strategy["matched_signals"] = matched
    strategy["selection_reason"] = "; ".join(str(item) for item in matched if str(item).strip())


def _enrich_reuse_with_continuity(
    strategy: dict[str, Any],
    *,
    handoff: dict[str, Any],
    decisions: list[dict[str, Any]],
    failures: list[dict[str, Any]],
    semantic_repo: dict[str, Any],
) -> dict[str, Any]:
    if not strategy:
        return strategy
    enriched = dict(strategy)
    strategy_paths = set(_strategy_paths(enriched))
    breakdown = dict(enriched.get("similarity_breakdown") if isinstance(enriched.get("similarity_breakdown"), dict) else {})
    flags = {
        "handoff_match": False,
        "recent_decision_support": False,
        "known_failure_avoidance": False,
        "semantic_subsystem_match": False,
    }
    avoidance_warnings: list[str] = []

    handoff_paths = set(_clean_string_list(handoff.get("recommended_starting_points"), limit=12))
    handoff_overlap = sorted(strategy_paths.intersection(handoff_paths))
    if handoff_overlap:
        flags["handoff_match"] = True
        _append_signal(enriched, "handoff_match:" + ",".join(handoff_overlap[:3]))
        breakdown["handoff_match"] = len(handoff_overlap)

    for decision in decisions:
        decision_paths = set(_clean_string_list(decision.get("related_paths"), limit=12))
        if strategy_paths.intersection(decision_paths):
            flags["recent_decision_support"] = True
            decision_signal = str(decision.get("subsystem") or decision.get("execution_id") or "recent_decision").strip()
            _append_signal(enriched, f"recent_decision_support:{decision_signal}")
            breakdown["recent_decision_support"] = int(breakdown.get("recent_decision_support", 0) or 0) + 1
            break

    for subsystem in semantic_repo.get("subsystems", []) if isinstance(semantic_repo.get("subsystems"), list) else []:
        if not isinstance(subsystem, dict):
            continue
        semantic_paths = set(
            _clean_string_list(subsystem.get("key_paths"), limit=12)
            + _clean_string_list(subsystem.get("entry_points"), limit=8)
        )
        if strategy_paths.intersection(semantic_paths):
            flags["semantic_subsystem_match"] = True
            _append_signal(enriched, f"semantic_subsystem_match:{subsystem.get('name')}")
            breakdown["semantic_subsystem_match"] = int(breakdown.get("semantic_subsystem_match", 0) or 0) + 1
            break

    for failure in failures:
        failure_paths = set(
            _clean_string_list(failure.get("related_paths"), limit=12)
            + _clean_string_list(failure.get("files_involved"), limit=12)
        )
        if strategy_paths.intersection(failure_paths):
            flags["known_failure_avoidance"] = True
            failure_id = str(failure.get("failure_id") or failure.get("failure_signature") or failure.get("signature") or "failure").strip()
            _append_signal(enriched, f"known_failure_avoidance:{failure_id}")
            avoidance_warnings.append(f"avoid_known_failure:{failure_id}")
            break

    if flags["known_failure_avoidance"]:
        breakdown["known_failure_avoidance"] = 0
    enriched["similarity_breakdown"] = breakdown
    enriched["cross_memory_reuse"] = flags
    enriched["avoidance_warnings"] = avoidance_warnings
    return enriched


def load_continuity_context(
    repo_root: Path,
    *,
    session_identity: dict[str, Any] | None = None,
    task_type: str = "",
    request_text: str = "",
    files: list[str] | None = None,
    primary_entry_point: str | None = None,
    commands: list[str] | None = None,
    tests: list[str] | None = None,
    errors: list[str] | None = None,
    area_id: str = "",
    max_decisions: int = 5,
    max_failures: int = 5,
) -> dict[str, Any]:
    warnings: list[str] = []
    session = _session_from_payload(session_identity, repo_root, warnings)
    preferences = _read_optional_json(repo_root, REPO_MEMORY_DIR / "user_preferences.json", dict, warnings)
    staleness = _read_optional_json(repo_root, STALENESS_PATH, dict, warnings)
    handoff = _read_optional_json(repo_root, HANDOFF_PATH, dict, warnings)
    if _handoff_is_stale(staleness):
        handoff = {}
    stale_decisions = _stale_decision_refs(staleness)
    raw_decisions = _read_optional_jsonl(repo_root, DECISIONS_PATH, warnings)
    decisions = [
        decision
        for index, decision in enumerate(raw_decisions)
        if _decision_ref(decision, index) not in stale_decisions
    ][-max_decisions:]
    semantic_repo = _load_semantic_repo(
        repo_root,
        warnings,
        request_text=request_text,
        files=list(files or []),
        area_id=str(area_id or ""),
        stale_subsystems=_stale_subsystem_names(staleness),
    )
    failures = lookup_failures(
        repo_root,
        task_type=str(task_type or ""),
        text=str(request_text or ""),
        files=list(files or []),
        area_id=str(area_id or ""),
        limit=max_failures,
    )
    reuse_files = _continuity_reuse_files(
        files=list(files or []),
        handoff=handoff,
        decisions=decisions,
        semantic_repo=semantic_repo,
    )
    procedural_reuse = select_strategy(
        repo_root,
        str(task_type or "") or None,
        files=reuse_files,
        primary_entry_point=primary_entry_point,
        request_text=request_text,
        commands=list(commands or []),
        tests=list(tests or []),
        errors=list(errors or []),
        area_id=area_id,
        exclude_task_ids=_stale_strategy_ids(staleness),
    ) or {}
    procedural_reuse = _enrich_reuse_with_continuity(
        procedural_reuse,
        handoff=handoff,
        decisions=decisions,
        failures=failures,
        semantic_repo=semantic_repo,
    )
    loaded = {
        "session": bool(session),
        "handoff": bool(handoff),
        "decisions": bool(decisions),
        "failures": bool(failures),
        "preferences": bool(preferences),
        "semantic_repo": bool(semantic_repo),
        "procedural_reuse": bool(procedural_reuse),
    }
    ranked_items = build_ranked_continuity_items(
        repo_root,
        request_text=request_text,
        files=list(files or []),
        handoff=handoff,
        decisions=decisions,
        failures=failures,
        semantic_repo=semantic_repo,
        procedural_reuse=procedural_reuse,
        staleness=staleness,
    )
    if any(str(item.get("kind") or "") == "repo_map" for item in ranked_items if isinstance(item, dict)):
        loaded["repo_map"] = True
    why_loaded = _why_loaded_from_items(loaded=loaded, ranked_items=ranked_items, staleness=staleness)
    active_work_state = compact_work_state_for_prepare(load_active_work_state(repo_root))
    if active_work_state:
        loaded["work_state"] = True
    recent_work_state = {}
    if not active_work_state:
        recent_work_state = compact_work_state_for_prepare(load_recent_inactive_work_state(repo_root))
    continuity_brief = build_continuity_brief(
        ranked_items=ranked_items,
        handoff=handoff,
        decisions=decisions,
        failures=failures,
        semantic_repo=semantic_repo,
        procedural_reuse=procedural_reuse,
        why_loaded=why_loaded,
        active_work_state=active_work_state,
        recent_work_state=recent_work_state,
    )
    context = {
        "agent_identity": session,
        "session": session,
        "loaded": loaded,
        "handoff": handoff,
        "decisions": decisions,
        "failures": failures,
        "semantic_repo": semantic_repo,
        "preferences": preferences,
        "procedural_reuse": procedural_reuse,
        "staleness": staleness,
        "ranked_items": ranked_items,
        "why_loaded": why_loaded,
        "continuity_brief": continuity_brief,
        "active_work_state": active_work_state,
        "recent_work_state": recent_work_state,
        "warnings": warnings,
    }
    context["startup_banner_render_payload"] = build_startup_banner_render_payload(context, repo_root)
    context["startup_banner_text"] = render_startup_banner(context, repo_root)
    context["continuity_summary_text"] = render_continuity_summary(context, repo_root)
    return context


def _resume_source(relative_path: Path, repo_root: Path) -> str:
    return relative_path.as_posix() if (repo_root / relative_path).exists() else ""


def _resume_item_text(item: dict[str, Any]) -> str:
    title = str(item.get("title") or item.get("id") or "").strip()
    reasons = _clean_string_list(item.get("reasons"), limit=2)
    if reasons:
        return f"{title} ({', '.join(reasons)})" if title else ", ".join(reasons)
    return title


def _resume_entry(path: str, reason: str) -> dict[str, str]:
    return {"path": str(path or "").strip(), "reason": str(reason or "").strip() or "relevant continuity signal"}


def _resume_is_action_path(path: str) -> bool:
    normalized = str(path or "").strip().replace("\\", "/")
    return bool(normalized) and normalized != ".aictx" and not normalized.startswith(".aictx/")


_RESUME_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in", "into", "is", "it", "of", "on", "or", "the", "to", "with",
    "this", "that", "these", "those", "current", "previous", "task", "work", "file", "files", "please", "run", "execute",
}


def _resume_request_terms(text: str) -> set[str]:
    terms = re.findall(r"[a-z0-9]+", str(text or "").lower())
    return {term for term in terms if len(term) > 2 and term not in _RESUME_STOPWORDS}


def _resume_task_profile(request_text: str) -> dict[str, Any]:
    haystack = str(request_text or "").lower()
    categories: dict[str, tuple[str, ...]] = {
        "implementation": (
            "fix", "bug", "implement", "change", "add", "update behavior", "refactor", "function", "module", "code",
        ),
        "testing": (
            "validate", "test", "tests", "pytest", "coverage", "edge case", "edge cases", "failing test",
        ),
        "documentation": (
            "readme", "docs", "documentation", "quickstart", "usage guide", "copy", "markdown", "instructions",
        ),
        "config": (
            "config", "configuration", "pyproject", "package", "dependency", "dependencies", "ci", "workflow", "github actions", "build", "lint", "ruff", "pytest config",
        ),
        "release": (
            "release", "version", "changelog", "tag", "publish", "pypi", "packaging",
        ),
        "analysis": (
            "metrics", "report", "usage report", "codex_usage", "session metrics", "demo metrics", "analysis", "analyze", "compare", "benchmark", "token usage",
        ),
    }
    scores = {category: sum(1 for signal in signals if signal in haystack) for category, signals in categories.items()}
    best_category = "unknown"
    best_score = 0
    for category in ("analysis", "release", "config", "documentation", "testing", "implementation"):
        score = scores.get(category, 0)
        if score > best_score:
            best_category = category
            best_score = score
    return {
        "task_category": best_category,
        "request_terms": _resume_request_terms(request_text),
        "explicit_metrics": scores.get("analysis", 0) > 0,
    }


def _resume_path_category(path: str) -> str:
    normalized = str(path or "").strip().replace("\\", "/").lower()
    name = normalized.rsplit("/", 1)[-1]
    if normalized == ".aictx" or normalized.startswith(".aictx/"):
        return "runtime_internal"
    if name in {"resume_capsule.md", "resume_capsule.json"} or normalized.endswith("/resume_capsule.md") or normalized.endswith("/resume_capsule.json"):
        return "generated_artifact"
    if (
        normalized.startswith(".demo_metrics/")
        or normalized.startswith("demo_metrics/")
        or normalized.startswith(".demo_results/")
        or normalized.startswith("demo_results/")
        or name.startswith("codex_usage") and name.endswith(".json")
        or "usage_report" in name and name.endswith(".json")
        or re.fullmatch(r"session_[^/]*_metrics\.json", name)
        or name.endswith("_metrics.json")
    ):
        return "telemetry_metrics"
    if normalized.startswith("tests/") or "/tests/" in f"/{normalized}":
        return "tests"
    if normalized.startswith("src/") or "/src/" in f"/{normalized}":
        return "source"
    if normalized == "readme.md" or normalized.startswith("docs/") or name.endswith(".md"):
        return "docs"
    if normalized.startswith(".github/workflows/"):
        return "ci"
    if name in {"pyproject.toml", "setup.cfg", "setup.py", "tox.ini", "pytest.ini", "ruff.toml", ".pre-commit-config.yaml"}:
        return "config"
    if normalized.startswith("examples/"):
        return "examples"
    return "unknown"


def _resume_path_score(entry: dict[str, str], *, profile: dict[str, Any], index: int, repo_root: Path | None = None) -> int:
    path = str(entry.get("path") or "").strip()
    if not _resume_is_action_path(path):
        return -10000
    category = str(profile.get("task_category") or "unknown")
    path_category = _resume_path_category(path)
    terms = profile.get("request_terms") if isinstance(profile.get("request_terms"), set) else set()
    searchable = " ".join([path, path.replace("/", " ").replace("_", " ").replace("-", " "), str(entry.get("reason") or "")]).lower()
    overlap = sum(1 for term in terms if term in searchable)
    score = 100 - index
    score += overlap * 8
    if repo_root is not None and _path_exists(repo_root, path):
        score += 5

    reason = str(entry.get("reason") or "").lower()
    if "active work state" in reason:
        score += 25
    elif "previous handoff" in reason:
        score += 15
    elif "repo_map" in reason or "repomap" in reason:
        score += 10
    elif "probable continuity" in reason:
        score += 5

    if category == "testing":
        score += {"tests": 35, "source": 24, "config": 4, "ci": 4, "docs": -18, "examples": -4}.get(path_category, 0)
    elif category == "implementation":
        score += {"source": 34, "tests": 30, "config": 4, "ci": 4, "docs": -18, "examples": -4}.get(path_category, 0)
    elif category == "documentation":
        score += {"docs": 35, "examples": 10, "source": -6, "tests": -8}.get(path_category, 0)
    elif category == "config":
        score += {"config": 35, "ci": 32, "source": -2, "tests": -4, "docs": -8}.get(path_category, 0)
    elif category == "release":
        score += {"config": 16, "docs": 12, "ci": 8, "source": -4, "tests": -6}.get(path_category, 0)
    elif category == "analysis":
        score += {"telemetry_metrics": 35, "docs": 8, "source": -8, "tests": -8}.get(path_category, 0)

    if path_category == "runtime_internal":
        score -= 10000
    elif path_category == "generated_artifact":
        score -= 90
    elif path_category == "telemetry_metrics" and not bool(profile.get("explicit_metrics")):
        score -= 90
    elif path_category == "telemetry_metrics":
        score += 15
    if category in {"implementation", "testing"} and path_category == "docs":
        score -= 12
    return score


def _resume_rank_entries(entries: list[dict[str, str]], *, profile: dict[str, Any], limit: int, repo_root: Path | None = None) -> list[dict[str, str]]:
    cleaned = _resume_clean_entries(entries, limit=max(len(entries), limit))
    indexed = [(index, entry) for index, entry in enumerate(cleaned)]
    indexed.sort(key=lambda row: (-_resume_path_score(row[1], profile=profile, index=row[0], repo_root=repo_root), row[0]))
    return [entry for _, entry in indexed[:limit]]


def _resume_clean_entries(entries: list[dict[str, str]], *, limit: int) -> list[dict[str, str]]:
    cleaned: list[dict[str, str]] = []
    seen: set[str] = set()
    for entry in entries:
        path = str(entry.get("path") or "").strip()
        if not _resume_is_action_path(path) or path in seen:
            continue
        cleaned.append(entry)
        seen.add(path)
        if len(cleaned) >= limit:
            break
    return cleaned


def _resume_collect_entry_points(repo_root: Path, context: dict[str, Any], *, limit: int, profile: dict[str, Any]) -> tuple[list[dict[str, str]], list[dict[str, str]], list[str]]:
    warnings: list[str] = []
    ranked = context.get("ranked_items") if isinstance(context.get("ranked_items"), list) else []
    handoff = context.get("handoff") if isinstance(context.get("handoff"), dict) else {}
    active = context.get("active_work_state") if isinstance(context.get("active_work_state"), dict) else {}
    brief = context.get("continuity_brief") if isinstance(context.get("continuity_brief"), dict) else {}

    candidates: list[dict[str, str]] = []
    for path in _clean_string_list(active.get("active_files"), limit=5):
        candidates.append(_resume_entry(path, "active Work State file"))
    for path in _clean_string_list(handoff.get("recommended_starting_points"), limit=5):
        candidates.append(_resume_entry(path, "previous handoff starting point"))
    for item in ranked:
        if not isinstance(item, dict):
            continue
        reason = str(item.get("kind") or "continuity")
        for path in _clean_string_list(item.get("paths"), limit=3):
            candidates.append(_resume_entry(path, f"{reason}: {_resume_item_text(item)}"))
    for path in _clean_string_list(brief.get("probable_paths"), limit=8):
        candidates.append(_resume_entry(path, "probable continuity path"))

    live: list[dict[str, str]] = []
    fallback: list[dict[str, str]] = []
    seen: set[str] = set()
    for candidate in candidates:
        path = candidate["path"]
        if not _resume_is_action_path(path) or path in seen:
            continue
        seen.add(path)
        if _path_exists(repo_root, path):
            live.append(candidate)
        else:
            if "previous handoff" in candidate["reason"]:
                warnings.append(f"missing_entry_point:{path}")
                continue
            fallback.append(candidate)
        if len(live) >= limit and len(fallback) >= limit:
            break
    return (
        _resume_rank_entries(live, profile=profile, limit=limit, repo_root=repo_root),
        _resume_rank_entries(fallback, profile=profile, limit=limit, repo_root=repo_root),
        _clean_string_list(warnings, limit=5),
    )


def _resume_repo_map_slice(context: dict[str, Any], *, limit: int, profile: dict[str, Any], repo_root: Path | None = None) -> dict[str, list[dict[str, str]]]:
    ranked = context.get("ranked_items") if isinstance(context.get("ranked_items"), list) else []
    repo_items = [item for item in ranked if isinstance(item, dict) and str(item.get("kind") or "") == "repo_map"]
    candidates: list[dict[str, str]] = []
    for item in repo_items[: max(limit * 2, 1)]:
        reason = ", ".join(_clean_string_list(item.get("reasons"), limit=3)) or "RepoMap match"
        for path in _clean_string_list(item.get("paths"), limit=2):
            if not _resume_is_action_path(path):
                continue
            candidates.append(_resume_entry(path, reason))
    rows = _resume_rank_entries(candidates, profile=profile, limit=limit, repo_root=repo_root)
    return {"primary": rows[:1], "secondary": rows[1:], "avoid": []}

def _resume_startup_guard() -> dict[str, Any]:
    return {
        "resume_is_self_contained": True,
        "do_not_read_runtime_files": True,
        "do_not_inspect_aictx_installation": True,
        "allowed_aictx_commands_before_first_task_action": ["resume"],
        "allowed_aictx_commands_after_task_action": ["finalize"],
        "forbidden_normal_flow": [
            "aictx internal execution finalize",
            "direct shell calls to finalize_execution",
        ],
        "forbidden_before_first_task_action": [
            ".aictx/agent_runtime.md",
            ".aictx/**",
            "local/global AICTX installation files",
            "aictx -h",
            "aictx internal",
            "aictx reuse",
            "aictx suggest",
            "aictx next",
            "aictx task",
            "aictx messages",
            "aictx report",
            "aictx reflect",
        ],
        "exceptions": [
            "user explicitly asks for AICTX diagnostics",
            "current task is about AICTX itself",
            "resume output is missing/corrupt/contradictory",
            "finalization/update lifecycle requires it",
        ],
    }


def _resume_first_action(
    *,
    entry_points: list[dict[str, str]],
    fallback_entry_points: list[dict[str, str]],
    repo_map: dict[str, list[dict[str, str]]],
) -> dict[str, str]:
    candidates: list[dict[str, str]] = []
    candidates.extend(entry_points)
    candidates.extend(list(repo_map.get("primary") or []))
    candidates.extend(list(repo_map.get("secondary") or []))
    candidates.extend(fallback_entry_points)
    cleaned = _resume_clean_entries(candidates, limit=1)
    if cleaned:
        first = cleaned[0]
        return {"type": "open_file", "path": first["path"], "reason": first["reason"]}
    return {
        "type": "inspect_entry_points",
        "path": "",
        "reason": "No single high-confidence entry point was available; inspect the listed primary entry points.",
    }


def _resume_task_state(repo_root: Path, context: dict[str, Any], request_text: str, entry_points: list[dict[str, str]], broken: list[str]) -> dict[str, str]:
    active = context.get("active_work_state") if isinstance(context.get("active_work_state"), dict) else {}
    recent = context.get("recent_work_state") if isinstance(context.get("recent_work_state"), dict) else {}
    handoff = context.get("handoff") if isinstance(context.get("handoff"), dict) else {}
    ranked = context.get("ranked_items") if isinstance(context.get("ranked_items"), list) else []

    status = "unknown"
    reason = "No active Work State or handoff status available."
    if active:
        status = "active"
        reason = "Active Work State is present."
    elif str(recent.get("status") or "").strip() in {"blocked", "paused"}:
        status = "blocked"
        reason = f"Recent Work State is {recent.get('status')}."
    elif handoff:
        handoff_status = str(handoff.get("status") or "resolved").strip().lower()
        if handoff_status in {"resolved", "completed", "success"}:
            status = "completed"
            reason = "Previous handoff is completed; use as background."
        elif handoff_status in {"failed", "unresolved", "blocked"}:
            status = "blocked"
            reason = f"Previous handoff status is {handoff_status}."
        else:
            status = "unknown"
            reason = f"Previous handoff status is {handoff_status or 'unknown'}."

    confidence = "low"
    if active and (active.get("next_action") or entry_points):
        confidence = "high"
    elif entry_points or ranked:
        confidence = "medium"
    if broken:
        confidence = "low" if not entry_points else "medium"
        reason += " Some prior entry points are missing."
    if request_text and status == "completed":
        confidence = "medium" if entry_points or ranked else "low"
        reason += " Current request wins over completed prior work."
    if active and entry_points and not _path_exists(repo_root, str(entry_points[0].get("path") or "")):
        confidence = "medium"
    return {"status": status, "confidence": confidence, "reason": reason.strip()}


def _resume_strategy_text(strategy: dict[str, Any]) -> str:
    if not strategy:
        return "None relevant"
    confidence = strategy_reuse_confidence(strategy)
    reason = str(strategy.get("selection_reason") or "").strip()
    points = _resume_clean_entries(
        [_resume_entry(path, "strategy path") for path in (
            _clean_string_list(strategy.get("entry_points"), limit=4)
            + _clean_string_list(strategy.get("files_used"), limit=4)
            + _clean_string_list(strategy.get("tests_executed"), limit=4)
        )],
        limit=3,
    )
    starting = ", ".join(entry["path"] for entry in points)
    if starting:
        return f"Start from {starting}; matched prior successful work ({confidence} confidence: {reason or 'strategy reuse'})."
    return f"Reuse confidence {confidence}. {reason or 'Prior successful strategy matched.'}".strip()


def _render_resume_capsule_markdown(payload: dict[str, Any], *, full: bool = False) -> str:
    capsule = payload.get("capsule") if isinstance(payload.get("capsule"), dict) else {}
    task_state = payload.get("task_state") if isinstance(payload.get("task_state"), dict) else {}
    sources = payload.get("sources") if isinstance(payload.get("sources"), dict) else {}
    written = payload.get("written_files") if isinstance(payload.get("written_files"), dict) else {}
    first_action = capsule.get("first_action") if isinstance(capsule.get("first_action"), dict) else {}
    startup_banner_text = str(payload.get("startup_banner_text") or "").strip()
    lines = [
        "AICTX continuity capsule",
        "",
        "Startup banner to render",
    ]
    if startup_banner_text:
        lines.extend(startup_banner_text.splitlines())
    else:
        lines.append("- None; startup_banner_policy.show_in_first_user_visible_response is false.")
    lines.extend([
        "",
        "Startup rule",
        "This capsule is the operational brief for this task.",
        "Do not read `.aictx/agent_runtime.md` during normal startup.",
        "Do not inspect `.aictx/**`.",
        "Do not inspect local/global AICTX installation files.",
        "Do not inspect AICTX source unless the current user task is about AICTX itself.",
        "Run no further AICTX discovery commands before opening the first action target.",
        'After completing the task, use `aictx finalize --repo . --status success|failure --summary "<what happened>" --json`.',
        "",
        "First action",
    ])
    if first_action:
        action_type = str(first_action.get("type") or "inspect_entry_points")
        action_path = str(first_action.get("path") or "").strip()
        if action_type == "open_file" and action_path:
            lines.append(f"Open {action_path}.")
        elif action_type == "follow_current_request":
            lines.append("Follow the current user request.")
        elif action_type == "ask_clarification":
            lines.append("Ask the user for clarification.")
        else:
            lines.append("Inspect the listed primary entry points.")
        lines.extend(["", "Reason", str(first_action.get("reason") or "No reason provided.")])
    else:
        lines.extend(["Inspect the listed primary entry points.", "", "Reason", "No first action was provided."])
    lines.extend([
        "",
        "Current request",
        str(capsule.get("current_request") or "None provided"),
        "",
        "Task state",
        f"status: {task_state.get('status', 'unknown')}",
        f"confidence: {task_state.get('confidence', 'low')}",
        f"reason: {task_state.get('reason', 'unknown')}",
        "",
        "Resuming",
        str(capsule.get("resuming") or "No active continuation selected."),
        "",
        "Last progress",
        str(capsule.get("last_progress") or "None available"),
        "",
        "Next action",
        str(capsule.get("next_action") or "Use the current request and entry points below."),
        "",
        "Entry points",
    ])
    entry_points = list(capsule.get("entry_points") or []) + list(capsule.get("fallback_entry_points") or [])
    if entry_points:
        for index, item in enumerate(entry_points[: (8 if full else 5)], start=1):
            if isinstance(item, dict):
                lines.append(f"{index}. {item.get('path')} — {item.get('reason')}")
    else:
        lines.append("- None identified")

    repo_map = capsule.get("repo_map") if isinstance(capsule.get("repo_map"), dict) else {}
    lines.extend(["", "Relevant RepoMap"])
    repo_rows = list(repo_map.get("primary") or []) + list(repo_map.get("secondary") or [])
    if repo_rows:
        for item in repo_rows[: (8 if full else 4)]:
            if isinstance(item, dict):
                lines.append(f"- {item.get('path')}: {item.get('reason')}")
    else:
        lines.append("- None relevant")

    for title, key in (
        ("Already validated", "validated"),
        ("Relevant failures", "failures"),
        ("Relevant decisions", "decisions"),
    ):
        lines.extend(["", title])
        values = _clean_string_list(capsule.get(key), limit=(8 if full else 3))
        lines.extend([f"- {item}" for item in values] if values else ["- None relevant"])

    lines.extend(["", "Strategy", str(capsule.get("strategy") or "None relevant"), "", "Avoid"])
    for item in _clean_string_list(capsule.get("avoid"), limit=(10 if full else 6)):
        lines.append(f"- {item}")

    lines.extend(["", "Source index"])
    source_lines = [
        ("Full capsule", written.get("markdown")),
        ("Structured capsule", written.get("json")),
        ("Handoff", sources.get("handoff")),
        ("Last summary", sources.get("last_execution_summary")),
        ("Work state", sources.get("work_state")),
        ("RepoMap", sources.get("repo_map")),
    ]
    for label, value in source_lines:
        if value:
            lines.append(f"- {label}: {value}")
    warnings = _clean_string_list(payload.get("warnings"), limit=8)
    if warnings:
        lines.extend(["", "Warnings"])
        lines.extend([f"- {warning}" for warning in warnings])
    return "\n".join(lines).rstrip() + "\n"


def _resume_with_budget(payload: dict[str, Any], *, full: bool, max_chars: int) -> tuple[str, dict[str, Any]]:
    rendered = _render_resume_capsule_markdown(payload, full=full)
    if full or len(rendered) <= max_chars:
        return rendered, payload
    compact = json.loads(json.dumps(payload))
    capsule = compact.get("capsule") if isinstance(compact.get("capsule"), dict) else {}
    capsule["validated"] = _clean_string_list(capsule.get("validated"), limit=2)
    capsule["failures"] = _clean_string_list(capsule.get("failures"), limit=2)
    capsule["decisions"] = _clean_string_list(capsule.get("decisions"), limit=2)
    capsule["fallback_entry_points"] = list(capsule.get("fallback_entry_points") or [])[:1]
    compact.setdefault("warnings", []).append("budget_trimmed")
    rendered = _render_resume_capsule_markdown(compact, full=False)
    return rendered[:max_chars].rstrip() + "\n", compact


def build_resume_capsule(
    repo_root: Path,
    request_text: str = "",
    *,
    full: bool = False,
    task_type: str = "",
    agent_id: str = "",
    adapter_id: str = "",
    session_id: str = "",
) -> dict[str, Any]:
    repo_root = Path(repo_root).expanduser().resolve()
    request = str(request_text or "").strip()
    session_identity = touch_session_identity(
        repo_root,
        agent_id=agent_id,
        adapter_id=adapter_id or agent_id,
        session_id=session_id,
    )
    context = load_continuity_context(
        repo_root,
        session_identity=session_identity,
        request_text=request,
        task_type=task_type,
        max_decisions=8 if full else 5,
        max_failures=8 if full else 5,
    )
    limit = 8 if full else 4
    profile = _resume_task_profile(request)
    entry_points, fallback_entry_points, entry_warnings = _resume_collect_entry_points(repo_root, context, limit=limit, profile=profile)
    repo_map = _resume_repo_map_slice(context, limit=limit, profile=profile, repo_root=repo_root)
    task_state = _resume_task_state(repo_root, context, request, entry_points, entry_warnings)

    active = context.get("active_work_state") if isinstance(context.get("active_work_state"), dict) else {}
    recent = context.get("recent_work_state") if isinstance(context.get("recent_work_state"), dict) else {}
    handoff = context.get("handoff") if isinstance(context.get("handoff"), dict) else {}
    brief = context.get("continuity_brief") if isinstance(context.get("continuity_brief"), dict) else {}
    strategy = context.get("procedural_reuse") if isinstance(context.get("procedural_reuse"), dict) else {}

    if active:
        resuming = str(active.get("goal") or active.get("task_id") or "active Work State").strip()
    elif task_state["status"] == "completed":
        resuming = "Previous task is completed; treat continuity as background for the current request."
    elif recent:
        resuming = str(recent.get("goal") or recent.get("task_id") or "recent paused/blocked Work State").strip()
    else:
        resuming = str(handoff.get("summary") or "No active previous task detected.").strip()

    last_progress = "; ".join(_clean_string_list(handoff.get("completed"), limit=3)) or str(handoff.get("summary") or "").strip()
    next_action = str(active.get("next_action") or recent.get("next_action") or "").strip()
    if not next_action and not (task_state["status"] == "completed" and request):
        next_action = _clean_string_list(handoff.get("next_steps"), limit=1)[0] if _clean_string_list(handoff.get("next_steps"), limit=1) else ""
    if not next_action and task_state["status"] == "completed" and request and entry_points:
        next_action = f"Use current request; start from {entry_points[0]['path']}"
    if not next_action and not (task_state["status"] == "completed" and request):
        where = _clean_string_list(brief.get("where_to_continue"), limit=1)
        next_action = where[0] if where and _resume_is_action_path(where[0]) else ""
    if not next_action and task_state["status"] == "completed" and request:
        next_action = "Use the current request; previous task is background."
    first_action = _resume_first_action(entry_points=entry_points, fallback_entry_points=fallback_entry_points, repo_map=repo_map)

    validated = _clean_string_list(
        list(active.get("verified", []) or [])
        + list(recent.get("verified", []) or [])
        + list(handoff.get("completed", []) or [])
        + [f"Test observed: {item}" for item in _clean_string_list(handoff.get("tests_observed"), limit=3)],
        limit=8 if full else 3,
    )
    failures = []
    for failure in context.get("failures", []) if isinstance(context.get("failures"), list) else []:
        if isinstance(failure, dict):
            text = str(failure.get("error_text") or failure.get("signature") or failure.get("failure_signature") or failure.get("failure_id") or "").strip()
            if text:
                failures.append(text)
    decisions = []
    for decision in context.get("decisions", []) if isinstance(context.get("decisions"), list) else []:
        if isinstance(decision, dict):
            text = str(decision.get("decision") or "").strip()
            if text:
                decisions.append(text)
    avoid = [
        "Do not inspect `.aictx/` during normal task execution.",
        "Do not run exploratory AICTX commands.",
        "Do not run `aictx internal` during normal task startup.",
        "Do not run `aictx -h`, `aictx reuse`, `aictx suggest`, `aictx next`, `aictx task`, `aictx messages`, or `aictx report` during normal task startup.",
    ]
    avoid.extend(f"Do not rely on missing prior entry point: {item.split(':', 1)[-1]}" for item in entry_warnings)

    sources = {
        "handoff": _resume_source(HANDOFF_PATH, repo_root),
        "last_execution_summary": _resume_source(LAST_EXECUTION_SUMMARY_PATH, repo_root),
        "work_state": ".aictx/tasks/active.json" if active else "",
        "repo_map": _resume_source(Path(".aictx/repo_map/index.json"), repo_root),
        "startup_banner": "load_continuity_context.startup_banner_text",
        "final_summary": "finalize_execution.agent_summary_text",
    }
    session = context.get("session") if isinstance(context.get("session"), dict) else {}
    session_key = str(session.get("session_id") or "")
    banner_already_shown = bool(session_key and str(session.get("banner_shown_session_id") or "") == session_key)
    startup_banner_text = "" if banner_already_shown else str(context.get("startup_banner_text") or "")
    startup_banner_render_payload = context.get("startup_banner_render_payload") if isinstance(context.get("startup_banner_render_payload"), dict) else {}
    payload: dict[str, Any] = {
        "schema_version": "1.0",
        "generated_at": _now_iso(),
        "mode": "agent_brief",
        "repo": repo_root.as_posix(),
        "request": request,
        "startup_banner_text": startup_banner_text,
        "startup_banner_render_payload": startup_banner_render_payload,
        "startup_banner_policy": {
            "source": "resume",
            "show_in_first_user_visible_response": bool(startup_banner_text.strip()),
            "already_shown": banner_already_shown,
            "render_payload_field": "startup_banner_render_payload",
            "data_source": "load_continuity_context",
            "does_not_replace_prepare_execution": True,
            "instruction": "Render this startup banner in the current user language at the top of the first substantive user-visible response. Prefer startup_banner_render_payload when available and use startup_banner_text only as fallback. Preserve exact facts, paths, commands, flags, package names, test names, code identifiers, and link targets. Do not satisfy this requirement only with a transient progress/status message that will be omitted from the final task response; if unsure, preserve the banner at the top of the final response.",
        },
        "startup_guard": _resume_startup_guard(),
        "budget": {"target_tokens": 1200, "estimated_tokens": 0, "chars": 0},
        "task_state": task_state,
        "capsule": {
            "current_request": request,
            "first_action": first_action,
            "resuming": resuming,
            "last_progress": last_progress,
            "next_action": next_action,
            "entry_points": entry_points,
            "fallback_entry_points": fallback_entry_points,
            "repo_map": repo_map,
            "validated": validated,
            "failures": _clean_string_list(failures, limit=8 if full else 3),
            "decisions": _clean_string_list(decisions, limit=8 if full else 3),
            "strategy": _resume_strategy_text(strategy),
            "avoid": avoid,
        },
        "sources": sources,
        "written_files": {
            "markdown": RESUME_CAPSULE_MARKDOWN_PATH.as_posix(),
            "json": RESUME_CAPSULE_JSON_PATH.as_posix(),
        },
        "warnings": _clean_string_list(list(context.get("warnings", []) or []) + entry_warnings, limit=12),
    }
    max_chars = 12000 if full else 6000
    markdown, payload = _resume_with_budget(payload, full=full, max_chars=max_chars)
    payload["budget"] = {
        "target_tokens": 2400 if full else 1200,
        "estimated_tokens": max(1, len(markdown) // 4),
        "chars": len(markdown),
    }
    json_path = repo_root / RESUME_CAPSULE_JSON_PATH
    markdown_path = repo_root / RESUME_CAPSULE_MARKDOWN_PATH
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(markdown, encoding="utf-8")
    write_json(json_path, payload)
    return payload


def render_resume_capsule(payload: dict[str, Any], *, full: bool = False) -> str:
    return _render_resume_capsule_markdown(payload, full=full)

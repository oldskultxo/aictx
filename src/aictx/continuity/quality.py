from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..failures import FAILURE_PATTERNS_PATH
from ..report import build_repo_map_report
from ..state import REPO_CONTINUITY_DIR, read_json, read_jsonl
from ..work_state import load_active_work_state, load_recent_inactive_work_state

HANDOFF_PATH = REPO_CONTINUITY_DIR / "handoff.json"
DECISIONS_PATH = REPO_CONTINUITY_DIR / "decisions.jsonl"
RESUME_CAPSULE_JSON_PATH = REPO_CONTINUITY_DIR / "resume_capsule.json"
CONTINUITY_VIEW_MARKDOWN_PATH = Path(".aictx") / "reports" / "continuity-view.md"

FRESH_MAX_DAYS = 7
POSSIBLY_STALE_MAX_DAYS = 30
DEMOTED_MAX_DAYS = 90


def _now(now: datetime | None) -> datetime:
    current = now or datetime.now(timezone.utc)
    return current.replace(tzinfo=timezone.utc) if current.tzinfo is None else current.astimezone(timezone.utc)


def _parse_iso(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def _age_days(value: Any, *, now: datetime) -> int | None:
    parsed = _parse_iso(value)
    if not parsed:
        return None
    return max(0, int((now - parsed).total_seconds() // 86400))


def _dedupe_strings(values: Any, *, limit: int = 12) -> list[str]:
    if not isinstance(values, list):
        values = [values] if values else []
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip().replace("\\", "/")
        if not text or text in seen:
            continue
        cleaned.append(text)
        seen.add(text)
        if len(cleaned) >= limit:
            break
    return cleaned


def _is_repo_relative_path(path: str) -> bool:
    text = str(path or "").strip().replace("\\", "/")
    return bool(text) and not text.startswith("/") and text != ".aictx" and not text.startswith(".aictx/") and not text.startswith("../")


def _missing_paths(repo_root: Path, paths: Any) -> list[str]:
    missing: list[str] = []
    for path in _dedupe_strings(paths, limit=24):
        if _is_repo_relative_path(path) and not (repo_root / path).exists():
            missing.append(path)
    return missing


def _issue(
    code: str,
    severity: str,
    source: str,
    summary: str,
    *,
    source_id: str = "",
    reason: str = "",
    related_paths: list[str] | None = None,
    age_days: int | None = None,
    recommendation: str = "",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "code": code,
        "severity": severity if severity in {"info", "warning", "error"} else "warning",
        "source": source,
        "source_id": source_id,
        "summary": summary,
        "reason": reason,
        "related_paths": related_paths or [],
        "recommendation": recommendation,
    }
    if age_days is not None:
        payload["age_days"] = age_days
    return payload


def _item_status(age_days: int | None, *, missing: bool = False, confidence: str = "", role: str = "") -> str:
    if missing:
        return "stale"
    if age_days is None:
        if confidence == "low" or role == "background":
            return "demoted"
        return "unverified"
    if age_days <= FRESH_MAX_DAYS:
        return "fresh"
    if age_days <= POSSIBLY_STALE_MAX_DAYS:
        return "possibly_stale"
    if age_days <= DEMOTED_MAX_DAYS:
        return "demoted"
    return "obsolete"


def _loaded_item_from_context(repo_root: Path, row: dict[str, Any], *, now: datetime) -> dict[str, Any]:
    paths = _dedupe_strings(row.get("related_paths"), limit=12)
    missing = _missing_paths(repo_root, paths)
    status = str(row.get("staleness") or "")
    status = {"recent": "possibly_stale", "old": "demoted"}.get(status, status)
    if not status or status == "unknown":
        status = _item_status(None, missing=bool(missing), confidence=str(row.get("confidence") or ""), role=str(row.get("role") or ""))
    if missing:
        status = "stale"
    return {
        "source": str(row.get("source") or row.get("kind") or ""),
        "source_id": str(row.get("source_id") or ""),
        "kind": str(row.get("kind") or ""),
        "summary": str(row.get("summary") or ""),
        "last_updated": "",
        "last_seen": "",
        "linked_files": paths,
        "linked_task_or_area": str(row.get("source_id") or ""),
        "confidence": str(row.get("confidence") or "unknown"),
        "relevance": str(row.get("role") or "background"),
        "why_loaded": str(row.get("selection_reason") or "; ".join(_dedupe_strings(row.get("match_reasons"), limit=6))),
        "staleness_status": status,
        "missing_files": missing,
    }


def _raw_loaded_items(repo_root: Path, *, now: datetime) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    active = load_active_work_state(repo_root)
    if isinstance(active, dict) and active:
        age = _age_days(active.get("updated_at"), now=now)
        paths = _dedupe_strings(active.get("active_files"), limit=12)
        items.append({
            "source": ".aictx/tasks/active.json",
            "source_id": str(active.get("task_id") or "active_work_state"),
            "kind": "work_state",
            "summary": str(active.get("goal") or active.get("next_action") or ""),
            "last_updated": str(active.get("updated_at") or ""),
            "last_seen": str(active.get("updated_at") or ""),
            "linked_files": paths,
            "linked_task_or_area": str(active.get("task_id") or ""),
            "confidence": "high",
            "relevance": "primary",
            "why_loaded": "active Work State",
            "staleness_status": _item_status(age, missing=bool(_missing_paths(repo_root, paths))),
            "missing_files": _missing_paths(repo_root, paths),
        })

    handoff = read_json(repo_root / HANDOFF_PATH, {})
    if isinstance(handoff, dict) and handoff:
        age = _age_days(handoff.get("updated_at") or handoff.get("timestamp"), now=now)
        paths = _dedupe_strings(handoff.get("recommended_starting_points"), limit=12)
        items.append({
            "source": HANDOFF_PATH.as_posix(),
            "source_id": str(handoff.get("source_execution_id") or "latest"),
            "kind": "handoff",
            "summary": str(handoff.get("summary") or ""),
            "last_updated": str(handoff.get("updated_at") or handoff.get("timestamp") or ""),
            "last_seen": str(handoff.get("updated_at") or handoff.get("timestamp") or ""),
            "linked_files": paths,
            "linked_task_or_area": str(handoff.get("source_execution_id") or ""),
            "confidence": "medium",
            "relevance": "background" if str(handoff.get("status") or "").lower() in {"resolved", "completed", "success"} else "carryover",
            "why_loaded": "latest handoff",
            "staleness_status": _item_status(age, missing=bool(_missing_paths(repo_root, paths))),
            "missing_files": _missing_paths(repo_root, paths),
        })

    for index, row in enumerate(read_jsonl(repo_root / DECISIONS_PATH)[-8:]):
        paths = _dedupe_strings(row.get("related_paths"), limit=12)
        age = _age_days(row.get("timestamp"), now=now)
        items.append({
            "source": DECISIONS_PATH.as_posix(),
            "source_id": str(row.get("execution_id") or f"decision:{index}"),
            "kind": "decision",
            "summary": str(row.get("decision") or ""),
            "last_updated": str(row.get("timestamp") or ""),
            "last_seen": str(row.get("timestamp") or ""),
            "linked_files": paths,
            "linked_task_or_area": str(row.get("subsystem") or ""),
            "confidence": "medium" if paths or row.get("subsystem") else "low",
            "relevance": "background",
            "why_loaded": "recent decision memory",
            "staleness_status": _item_status(age, missing=bool(_missing_paths(repo_root, paths)), confidence="medium" if paths else "low", role="background"),
            "missing_files": _missing_paths(repo_root, paths),
        })

    for index, row in enumerate(read_jsonl(repo_root / FAILURE_PATTERNS_PATH)[-8:]):
        paths = _dedupe_strings(list(row.get("related_paths", []) or []) + list(row.get("files_involved", []) or []), limit=12)
        age = _age_days(row.get("timestamp"), now=now)
        items.append({
            "source": FAILURE_PATTERNS_PATH.as_posix(),
            "source_id": str(row.get("failure_id") or row.get("signature") or f"failure:{index}"),
            "kind": "failure",
            "summary": str(row.get("error_text") or row.get("signature") or ""),
            "last_updated": str(row.get("timestamp") or ""),
            "last_seen": str(row.get("timestamp") or ""),
            "linked_files": paths,
            "linked_task_or_area": str(row.get("area_id") or row.get("task_type") or ""),
            "confidence": "medium" if paths or row.get("task_type") else "low",
            "relevance": "caution",
            "why_loaded": "failure memory",
            "staleness_status": _item_status(age, missing=bool(_missing_paths(repo_root, paths))),
            "missing_files": _missing_paths(repo_root, paths),
        })
    return items


def _existing_loaded_items(repo_root: Path, context: dict[str, Any], *, now: datetime) -> list[dict[str, Any]]:
    loaded = context.get("loaded_context") if isinstance(context.get("loaded_context"), list) else []
    rows = [_loaded_item_from_context(repo_root, row, now=now) for row in loaded if isinstance(row, dict)]
    return rows or _raw_loaded_items(repo_root, now=now)


def _add_issue(issues: list[dict[str, Any]], issue: dict[str, Any]) -> None:
    key = (issue["code"], issue.get("source"), issue.get("source_id"), tuple(issue.get("related_paths") or []))
    for existing in issues:
        existing_key = (existing["code"], existing.get("source"), existing.get("source_id"), tuple(existing.get("related_paths") or []))
        if existing_key == key:
            return
    issues.append(issue)


def _issue_category(code: Any) -> str:
    text = str(code or "unknown").strip()
    return text.split("_", 1)[0] if text else "unknown"


def _score_breakdown(issues: list[dict[str, Any]]) -> dict[str, Any]:
    penalties = {
        "error": 22,
        "warning": 10,
        "info": 2,
    }
    category_caps = {
        "missing": 24,
        "stale": 20,
        "obsolete": 20,
        "unverified": 20,
        "demoted": 6,
    }
    code_counts: dict[str, int] = {}
    category_totals: dict[str, int] = {}
    rows: list[dict[str, Any]] = []
    total_penalty = 0
    for item in issues:
        code = str(item.get("code") or "unknown")
        category = _issue_category(code)
        raw_points = penalties.get(str(item.get("severity") or "warning"), 10)
        code_counts[code] = code_counts.get(code, 0) + 1
        chargeable = code_counts[code] <= 2
        category_cap = category_caps.get(category, 30)
        category_total = category_totals.get(category, 0)
        remaining = max(0, category_cap - category_total)
        points = min(raw_points, remaining) if chargeable else 0
        category_totals[category] = category_total + points
        total_penalty += points
        rows.append({
            "code": code,
            "severity": str(item.get("severity") or "warning"),
            "category": category,
            "raw_points": raw_points,
            "points": points,
            "capped": points < raw_points,
        })
    score = max(0, min(100, 100 - total_penalty))
    return {
        "base_score": 100,
        "final_score": score,
        "total_penalty": total_penalty,
        "penalties": rows,
        "category_totals": category_totals,
        "caps": {"per_code_chargeable_items": 2, "category_caps": category_caps},
    }


def _score(issues: list[dict[str, Any]]) -> int:
    return int(_score_breakdown(issues)["final_score"])


def _bucket_items(loaded_items: list[dict[str, Any]], issues: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    buckets = {key: [] for key in ("fresh", "possibly_stale", "stale", "obsolete", "unverified", "demoted", "missing")}
    for item in loaded_items:
        status = str(item.get("staleness_status") or "unverified")
        if status not in buckets:
            status = "unverified"
        buckets[status].append(item)
        if item.get("missing_files"):
            buckets["missing"].append(item)
    for issue in issues:
        if issue.get("code", "").startswith("missing_"):
            buckets["missing"].append(issue)
        elif issue.get("code", "").startswith("obsolete_"):
            buckets["obsolete"].append(issue)
        elif issue.get("code", "").startswith("unverified_") or str(issue.get("severity")) == "info":
            buckets["unverified"].append(issue)
        elif issue.get("code", "").startswith("demoted_"):
            buckets["demoted"].append(issue)
        elif issue.get("severity") == "warning":
            buckets["possibly_stale"].append(issue)
        elif issue.get("severity") == "error":
            buckets["stale"].append(issue)
    return buckets


def _has_actionable_continuity(active: dict[str, Any], recent: dict[str, Any], loaded_items: list[dict[str, Any]]) -> bool:
    if active or recent:
        return True
    actionable = {"work_state", "handoff", "failure", "decision", "strategy"}
    return any(str(item.get("kind") or "") in actionable for item in loaded_items)


def _used_repomap(repo_map: dict[str, Any], loaded_items: list[dict[str, Any]]) -> bool:
    if bool(repo_map.get("enabled") or repo_map.get("used")):
        return True
    return any(str(item.get("kind") or "") == "repo_map" or "repo_map" in str(item.get("source") or "") for item in loaded_items)


def _collect_continuity_quality(
    repo_root: Path,
    *,
    context: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    repo = Path(repo_root).expanduser().resolve()
    current = _now(now)
    ctx = context if isinstance(context, dict) else {}
    issues: list[dict[str, Any]] = []
    loaded_items = _existing_loaded_items(repo, ctx, now=current)
    active = ctx.get("active_work_state") if isinstance(ctx.get("active_work_state"), dict) else load_active_work_state(repo)
    recent = ctx.get("recent_work_state") if isinstance(ctx.get("recent_work_state"), dict) else load_recent_inactive_work_state(repo)
    actionable_continuity = _has_actionable_continuity(active, recent, loaded_items)

    # Existing staleness logic remains the canonical detector for obsolete records;
    # this quality layer only summarizes/demotes and does not persist changes.
    try:
        from . import refresh_staleness

        staleness = refresh_staleness(
            repo,
            now=current,
            handoff_max_age_days=POSSIBLY_STALE_MAX_DAYS,
            persist=False,
        ).get("staleness", {})
    except Exception:
        staleness = {}
    if isinstance(staleness, dict):
        handoff_state = staleness.get("handoff") if isinstance(staleness.get("handoff"), dict) else {}
        if handoff_state.get("stale"):
            _add_issue(issues, _issue(
                "stale_handoff",
                "warning",
                HANDOFF_PATH.as_posix(),
                "Latest handoff may be stale.",
                reason="; ".join(_dedupe_strings(handoff_state.get("reasons"), limit=4)),
                recommendation="Treat the handoff as background unless the current task confirms it.",
            ))
        for row in staleness.get("decisions", []) if isinstance(staleness.get("decisions"), list) else []:
            if isinstance(row, dict) and row.get("stale"):
                _add_issue(issues, _issue(
                    "obsolete_decision",
                    "warning",
                    DECISIONS_PATH.as_posix(),
                    "Decision memory is superseded or points at missing files.",
                    source_id=str(row.get("ref") or ""),
                    reason="; ".join(_dedupe_strings(row.get("reasons"), limit=4)),
                    recommendation="Demote this decision unless current code inspection validates it.",
                ))

    repo_map = ctx.get("structural_context") if isinstance(ctx.get("structural_context"), dict) else build_repo_map_report(repo)
    if not bool(repo_map.get("query_available")):
        severity = "warning" if _used_repomap(repo_map, loaded_items) else "info"
        _add_issue(issues, _issue(
            "missing_repomap",
            severity,
            ".aictx/repo_map/index.json",
            "RepoMap is unavailable or not queryable.",
            reason=f"last_refresh_status:{repo_map.get('last_refresh_status') or 'never'}",
            recommendation="Run `aictx map refresh --repo . --json` when diagnostics are allowed.",
        ))

    view = ctx.get("continuity_view") if isinstance(ctx.get("continuity_view"), dict) else {}
    view_path = repo / CONTINUITY_VIEW_MARKDOWN_PATH
    if not view and view_path.exists():
        view = {"exists": True, "generated_at": datetime.fromtimestamp(view_path.stat().st_mtime, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")}
    if not bool(view.get("exists")):
        severity = "warning" if actionable_continuity else "info"
        _add_issue(issues, _issue(
            "missing_continuity_view",
            severity,
            CONTINUITY_VIEW_MARKDOWN_PATH.as_posix(),
            "Continuity View is not available.",
            recommendation="Run `aictx view --repo .` when an inspectable continuity view is needed.",
        ))
    else:
        view_age = _age_days(view.get("generated_at"), now=current)
        if view_age is not None and view_age > 14:
            _add_issue(issues, _issue(
                "stale_continuity_view",
                "warning",
                CONTINUITY_VIEW_MARKDOWN_PATH.as_posix(),
                "Continuity View may be stale.",
                age_days=view_age,
                recommendation="Regenerate the Continuity View after significant work.",
            ))

    for item in loaded_items:
        missing = _dedupe_strings(item.get("missing_files"), limit=8)
        if missing:
            _add_issue(issues, _issue(
                "missing_linked_file",
                "warning",
                str(item.get("source") or ""),
                "Continuity item references files that are no longer present.",
                source_id=str(item.get("source_id") or ""),
                reason="missing_paths:" + ",".join(missing[:5]),
                related_paths=missing,
                recommendation="Demote this item until current repo inspection validates it.",
            ))
        status = str(item.get("staleness_status") or "")
        if status in {"demoted", "obsolete"}:
            _add_issue(issues, _issue(
                f"{status}_loaded_context",
                "info" if status == "demoted" else "warning",
                str(item.get("source") or ""),
                "Loaded continuity should be treated as background.",
                source_id=str(item.get("source_id") or ""),
                related_paths=_dedupe_strings(item.get("linked_files"), limit=6),
                recommendation="Use as context only; verify against current files before acting.",
            ))

    if not active:
        _add_issue(issues, _issue(
            "missing_active_work_state",
            "info",
            ".aictx/tasks/active.json",
            "No active Work State is present.",
            reason="recent_work_state_available" if recent else "no_active_or_recent_work_state",
            recommendation="Start or update Work State for long-running tasks.",
        ))
    unverified = _dedupe_strings(active.get("unverified") if isinstance(active, dict) else [], limit=4) + _dedupe_strings(recent.get("unverified") if isinstance(recent, dict) else [], limit=4)
    if unverified:
        _add_issue(issues, _issue(
            "unverified_work_state",
            "warning",
            ".aictx/tasks",
            "Work State contains unverified continuity.",
            reason="; ".join(unverified[:4]),
            recommendation="Validate or demote unverified notes before relying on them.",
        ))

    contract = ctx.get("execution_contract") if isinstance(ctx.get("execution_contract"), dict) else {}
    carryover = ctx.get("carryover_gaps") if isinstance(ctx.get("carryover_gaps"), list) else []
    validated = []
    capsule = ctx.get("capsule") if isinstance(ctx.get("capsule"), dict) else {}
    if isinstance(capsule.get("validated"), list):
        validated.extend(str(item) for item in capsule.get("validated", []) if str(item or "").strip())
    missing_validation_carryover = [
        gap for gap in carryover
        if isinstance(gap, dict) and str(gap.get("kind") or "") == "missing_validation"
    ]
    for gap in missing_validation_carryover:
        _add_issue(issues, _issue(
            "missing_validation_evidence",
            "warning",
            ".aictx/continuity/contracts",
            "Validation evidence is missing for carried continuity.",
            source_id=str(gap.get("source_execution_id") or ""),
            reason=str(gap.get("summary") or gap.get("expected") or ""),
            recommendation=str(gap.get("next_action") or "Run the expected validation before relying on continuity."),
        ))
    if contract and not validated and not missing_validation_carryover:
        _add_issue(issues, _issue(
            "pending_validation_for_new_contract",
            "info",
            ".aictx/continuity/contracts",
            "Execution contract is pending validation.",
            reason=str(contract.get("test_command", {}).get("command") or "") if isinstance(contract.get("test_command"), dict) else "",
            recommendation="Run or record the expected validation during finalize.",
        ))

    return {"repo": repo, "current": current, "ctx": ctx, "issues": issues, "loaded_items": loaded_items}


def build_continuity_quality_report(
    repo_root: Path,
    *,
    request_text: str = "",
    task_type: str = "",
    context: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    collected = _collect_continuity_quality(repo_root, context=context, now=now)
    current = collected["current"]
    issues = collected["issues"]
    loaded_items = collected["loaded_items"]
    scoring_breakdown = _score_breakdown(issues)
    score = int(scoring_breakdown["final_score"])
    issue_severities = {str(item.get("severity") or "warning") for item in issues}
    status = "error" if score < 50 or "error" in issue_severities else "warning" if score < 80 or "warning" in issue_severities else "ok"
    buckets = _bucket_items(loaded_items, issues)
    return {
        "schema_version": "1.0",
        "generated_at": current.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "score": score,
        "status": status,
        "request": str(request_text or ""),
        "task_type": str(task_type or ""),
        "advisory_only": True,
        "scoring_breakdown": scoring_breakdown,
        "fresh": buckets["fresh"],
        "possibly_stale": buckets["possibly_stale"],
        "stale": buckets["stale"],
        "obsolete": buckets["obsolete"],
        "unverified": buckets["unverified"],
        "demoted": buckets["demoted"],
        "missing": buckets["missing"],
        "issues": issues,
        "loaded_items": loaded_items,
        "summary": {
            "fresh": len(buckets["fresh"]),
            "possibly_stale": len(buckets["possibly_stale"]),
            "stale": len(buckets["stale"]),
            "obsolete": len(buckets["obsolete"]),
            "unverified": len(buckets["unverified"]),
            "demoted": len(buckets["demoted"]),
            "missing": len(buckets["missing"]),
        },
        "thresholds": {
            "fresh_max_days": FRESH_MAX_DAYS,
            "possibly_stale_max_days": POSSIBLY_STALE_MAX_DAYS,
            "demoted_max_days": DEMOTED_MAX_DAYS,
        },
    }


def build_continuity_quality_issues(
    repo_root: Path,
    *,
    request_text: str = "",
    task_type: str = "",
    context: dict[str, Any] | None = None,
    now: datetime | None = None,
    limit: int = 12,
) -> dict[str, Any]:
    collected = _collect_continuity_quality(repo_root, context=context, now=now)
    current = collected["current"]
    all_issues = list(collected["issues"])
    issues = all_issues[: max(0, int(limit or 0))]
    score = _score(all_issues)
    severities = {str(item.get("severity") or "warning") for item in all_issues}
    status = "error" if score < 50 or "error" in severities else "warning" if score < 80 or "warning" in severities else "ok"
    return {
        "schema_version": "1.0",
        "generated_at": current.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "score": score,
        "status": status,
        "request": str(request_text or ""),
        "task_type": str(task_type or ""),
        "advisory_only": True,
        "issues": issues,
    }


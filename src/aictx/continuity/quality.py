from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..continuity_view import CONTINUITY_VIEW_PATH
from ..failures import FAILURE_PATTERNS_PATH, load_failures
from ..repo_map.config import is_repomap_enabled, load_repomap_index
from ..state import REPO_CONTINUITY_DIR, REPO_METRICS_DIR, REPO_STRATEGY_MEMORY_DIR, read_json, read_jsonl
from ..work_state import load_active_work_state_checked, load_recent_inactive_work_state

FRESH_MAX_DAYS = 7
POSSIBLY_STALE_MAX_DAYS = 30
DEMOTED_MAX_DAYS = 90

_DECISIONS_PATH = REPO_CONTINUITY_DIR / "decisions.jsonl"
_HANDOFF_PATH = REPO_CONTINUITY_DIR / "handoff.json"
_HANDOFFS_HISTORY_PATH = REPO_CONTINUITY_DIR / "handoffs.jsonl"
_LAST_EXECUTION_SUMMARY_PATH = REPO_CONTINUITY_DIR / "last_execution_summary.md"
_RESUME_CONTRACTS_PATH = REPO_CONTINUITY_DIR / "contracts"

_STATUSES = ("fresh", "possibly_stale", "stale", "obsolete", "unverified", "demoted", "missing")


def _now(now: datetime | None) -> datetime:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current


def _parse_time(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _age_days(value: Any, *, now: datetime) -> int | None:
    parsed = _parse_time(value)
    if not parsed:
        return None
    return max(0, int((now - parsed).total_seconds() // 86400))


def _repo_rel(path: Any) -> str:
    text = str(path or "").strip().replace("\\", "/")
    if not text or text.startswith("/") or text == "." or text.startswith(".aictx/") or text == ".aictx":
        return ""
    return text[2:] if text.startswith("./") else text


def _clean_strings(values: Any, *, limit: int = 12) -> list[str]:
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, list):
        return []
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
        if len(result) >= limit:
            break
    return result


def _linked_files(item: dict[str, Any]) -> list[str]:
    values: list[Any] = []
    for key in (
        "linked_files",
        "related_paths",
        "recommended_starting_points",
        "entry_points",
        "active_files",
        "files",
        "files_used",
        "touched_files",
    ):
        raw = item.get(key)
        if isinstance(raw, list):
            for value in raw:
                if isinstance(value, dict):
                    values.append(value.get("path"))
                else:
                    values.append(value)
        elif isinstance(raw, str):
            values.append(raw)
    first_action = item.get("first_action")
    if isinstance(first_action, dict):
        values.append(first_action.get("path"))
    elif isinstance(first_action, str):
        values.append(first_action)
    return [path for path in (_repo_rel(value) for value in values) if path]


def _missing_paths(repo_root: Path, paths: list[str]) -> list[str]:
    missing: list[str] = []
    for path in paths:
        if path and not (repo_root / path).exists() and path not in missing:
            missing.append(path)
    return missing


def _item_status(age_days: int | None, *, missing_paths: list[str] | None = None, unverified: bool = False) -> str:
    if missing_paths:
        return "stale"
    if unverified:
        return "unverified"
    if age_days is None:
        return "unverified"
    if age_days <= FRESH_MAX_DAYS:
        return "fresh"
    if age_days <= POSSIBLY_STALE_MAX_DAYS:
        return "possibly_stale"
    if age_days <= DEMOTED_MAX_DAYS:
        return "demoted"
    return "obsolete"


def _issue(
    code: str,
    severity: str,
    source: str,
    summary: str,
    reason: str,
    *,
    source_id: str = "",
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


def _loaded_item(
    *,
    source: str,
    source_id: str = "",
    last_updated: str = "",
    last_seen: str = "",
    linked_files: list[str] | None = None,
    linked_task_or_area: str = "",
    confidence: str = "medium",
    relevance: str = "medium",
    why_loaded: str = "available continuity signal",
    staleness_status: str = "unverified",
) -> dict[str, Any]:
    return {
        "source": source,
        "source_id": source_id,
        "last_updated": last_updated,
        "last_seen": last_seen,
        "linked_files": linked_files or [],
        "linked_task_or_area": linked_task_or_area,
        "confidence": confidence,
        "relevance": relevance,
        "why_loaded": why_loaded,
        "staleness_status": staleness_status,
    }


def _score_breakdown(issues: list[dict[str, Any]]) -> dict[str, Any]:
    weights = {"error": 24, "warning": 10, "info": 2}
    per_code_limit = 2
    category_caps = {"availability": 26, "freshness": 30, "validation": 28, "references": 30, "general": 20}
    categories = {
        "missing_repomap": "availability",
        "missing_continuity_view": "availability",
        "stale_continuity_view": "freshness",
        "old_context_demoted": "freshness",
        "obsolete_context": "freshness",
        "missing_validation_evidence": "validation",
        "pending_validation_for_new_contract": "validation",
        "partial_execution_contract": "validation",
        "deleted_file_reference": "references",
    }
    code_counts: dict[str, int] = {}
    raw_by_category: dict[str, int] = {}
    penalties: list[dict[str, Any]] = []
    for issue in issues:
        code = str(issue.get("code") or "")
        severity = str(issue.get("severity") or "info")
        count = code_counts.get(code, 0)
        code_counts[code] = count + 1
        chargeable = count < per_code_limit
        category = categories.get(code, "general")
        penalty = weights.get(severity, 6) if chargeable else 0
        raw_by_category[category] = raw_by_category.get(category, 0) + penalty
        penalties.append({"code": code, "severity": severity, "category": category, "penalty": penalty, "chargeable": chargeable})
    capped = {category: min(value, category_caps.get(category, value)) for category, value in raw_by_category.items()}
    total = sum(capped.values())
    return {
        "base_score": 100,
        "final_score": max(0, min(100, 100 - total)),
        "total_penalty": total,
        "penalties": penalties,
        "category_totals": capped,
        "caps": {"per_code_chargeable_items": per_code_limit, "category_caps": category_caps},
    }


def _status_from(score: int, issues: list[dict[str, Any]]) -> str:
    severities = {str(issue.get("severity") or "") for issue in issues}
    if "error" in severities or score < 50:
        return "error"
    if "warning" in severities or score < 80:
        return "warning"
    return "ok"


def _summary_counts(loaded_items: list[dict[str, Any]]) -> dict[str, int]:
    counts = {status: 0 for status in _STATUSES}
    for item in loaded_items:
        status = str(item.get("staleness_status") or "unverified")
        counts[status if status in counts else "unverified"] += 1
    return counts


def _context_dict(context: dict[str, Any] | None, key: str) -> dict[str, Any]:
    value = context.get(key) if isinstance(context, dict) else {}
    return value if isinstance(value, dict) else {}


def _context_list(context: dict[str, Any] | None, key: str) -> list[Any]:
    value = context.get(key) if isinstance(context, dict) else []
    return value if isinstance(value, list) else []


def build_continuity_quality_report(
    repo_root: Path,
    *,
    request_text: str = "",
    task_type: str = "",
    context: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build a deterministic, read-only continuity quality report."""
    repo = Path(repo_root).expanduser().resolve()
    current = _now(now)
    issues: list[dict[str, Any]] = []
    loaded_items: list[dict[str, Any]] = []

    active_checked = load_active_work_state_checked(repo)
    active = _context_dict(context, "active_work_state") or active_checked.get("active_work_state") if isinstance(active_checked, dict) else {}
    if not isinstance(active, dict):
        active = {}
    recent = _context_dict(context, "recent_work_state") or load_recent_inactive_work_state(repo)
    if not isinstance(recent, dict):
        recent = {}

    for source, state, why in (("work_state", active, "active Work State"), ("work_state", recent, "recent paused/blocked Work State")):
        if not state:
            continue
        last = str(state.get("updated_at") or state.get("created_at") or "")
        age = _age_days(last, now=current)
        files = _linked_files(state)
        missing = _missing_paths(repo, files)
        status = _item_status(age, missing_paths=missing, unverified=bool(state.get("unverified")))
        loaded_items.append(_loaded_item(
            source=source,
            source_id=str(state.get("task_id") or ""),
            last_updated=last,
            linked_files=files,
            linked_task_or_area=str(state.get("goal") or state.get("task_id") or ""),
            confidence="high" if source == "work_state" and state is active else "medium",
            relevance="high",
            why_loaded=why,
            staleness_status=status,
        ))
        if missing:
            issues.append(_issue("deleted_file_reference", "warning", source, "Continuity item references files that are no longer present.", "linked file path does not exist in the current repo", source_id=str(state.get("task_id") or ""), related_paths=missing, age_days=age, recommendation="Demote this item until current repo inspection validates it."))

    handoff = read_json(repo / _HANDOFF_PATH, {})
    if isinstance(handoff, dict) and handoff:
        last = str(handoff.get("updated_at") or handoff.get("timestamp") or "")
        age = _age_days(last, now=current)
        files = _linked_files(handoff)
        missing = _missing_paths(repo, files)
        status = _item_status(age, missing_paths=missing)
        loaded_items.append(_loaded_item(source="handoff", source_id=str(handoff.get("source_execution_id") or "current"), last_updated=last, linked_files=files, linked_task_or_area=str(handoff.get("summary") or ""), confidence="medium", relevance="medium", why_loaded="current handoff", staleness_status=status))
        if missing:
            issues.append(_issue("deleted_file_reference", "warning", _HANDOFF_PATH.as_posix(), "Continuity item references files that are no longer present.", "handoff linked path does not exist", related_paths=missing, age_days=age, recommendation="Demote this handoff until current repo inspection validates it."))

    for index, decision in enumerate(read_jsonl(repo / _DECISIONS_PATH)[-25:]):
        last = str(decision.get("timestamp") or decision.get("updated_at") or "")
        age = _age_days(last, now=current)
        files = _linked_files(decision)
        missing = _missing_paths(repo, files)
        status = _item_status(age, missing_paths=missing)
        source_id = str(decision.get("id") or decision.get("decision_id") or f"decision-{index}")
        loaded_items.append(_loaded_item(source="decision", source_id=source_id, last_updated=last, linked_files=files, linked_task_or_area=str(decision.get("subsystem") or decision.get("decision") or ""), confidence="medium", relevance="medium", why_loaded="recent decision", staleness_status=status))
        if missing:
            issues.append(_issue("deleted_file_reference", "warning", _DECISIONS_PATH.as_posix(), "Continuity item references files that are no longer present.", "decision related path does not exist", source_id=source_id, related_paths=missing, age_days=age, recommendation="Demote this decision until current repo inspection validates it."))

    for index, failure in enumerate(load_failures(repo)[-25:]):
        last = str(failure.get("timestamp") or failure.get("updated_at") or failure.get("last_seen") or "")
        age = _age_days(last, now=current)
        files = _linked_files(failure)
        missing = _missing_paths(repo, files)
        status = _item_status(age, missing_paths=missing)
        source_id = str(failure.get("failure_id") or failure.get("signature") or f"failure-{index}")
        loaded_items.append(_loaded_item(source="failure", source_id=source_id, last_updated=last, last_seen=str(failure.get("last_seen") or ""), linked_files=files, linked_task_or_area=str(failure.get("area_id") or ""), confidence="medium", relevance="medium", why_loaded="failure memory", staleness_status=status))
        if missing:
            issues.append(_issue("deleted_file_reference", "warning", FAILURE_PATTERNS_PATH.as_posix(), "Continuity item references files that are no longer present.", "failure memory related path does not exist", source_id=source_id, related_paths=missing, age_days=age, recommendation="Demote this failure memory until current repo inspection validates it."))

    for index, strategy in enumerate(read_jsonl(repo / REPO_STRATEGY_MEMORY_DIR / "strategies.jsonl")[-25:]):
        last = str(strategy.get("timestamp") or strategy.get("updated_at") or "")
        age = _age_days(last, now=current)
        files = _linked_files(strategy)
        missing = _missing_paths(repo, files)
        status = _item_status(age, missing_paths=missing)
        source_id = str(strategy.get("id") or f"strategy-{index}")
        loaded_items.append(_loaded_item(source="strategy", source_id=source_id, last_updated=last, linked_files=files, linked_task_or_area=str(strategy.get("task_type") or task_type or ""), confidence=str(strategy.get("reuse_confidence") or "medium"), relevance="medium", why_loaded="strategy memory", staleness_status=status))
        if missing:
            issues.append(_issue("deleted_file_reference", "warning", (REPO_STRATEGY_MEMORY_DIR / "strategies.jsonl").as_posix(), "Continuity item references files that are no longer present.", "strategy entry point does not exist", source_id=source_id, related_paths=missing, age_days=age, recommendation="Treat this strategy as background until repo inspection validates it."))

    # Availability checks.
    repomap_index = load_repomap_index(repo)
    repomap_files = repomap_index.get("files") if isinstance(repomap_index, dict) else []
    repomap_available = isinstance(repomap_files, list) and bool(repomap_files)
    repomap_used = bool(_context_dict(context, "repo_map") or _context_dict(context, "repo_map_status").get("used"))
    if repomap_available:
        loaded_items.append(_loaded_item(source="repomap", source_id="index", last_updated=str(repomap_index.get("updated_at") or repomap_index.get("generated_at") or ""), linked_files=[str(row.get("path") or "") for row in repomap_files[:8] if isinstance(row, dict)], confidence="high", relevance="high", why_loaded="RepoMap index available", staleness_status="fresh"))
    else:
        severity = "warning" if is_repomap_enabled(repo) or repomap_used else "info"
        issues.append(_issue("missing_repomap", severity, ".aictx/repo_map/index.json", "RepoMap is missing or unavailable.", "RepoMap index has no files", recommendation="Run `aictx map refresh --repo .` if RepoMap is expected for this repo."))

    continuity_view = _context_dict(context, "continuity_view")
    view_exists = bool(continuity_view.get("exists")) if continuity_view else (repo / CONTINUITY_VIEW_PATH).exists()
    view_generated_at = str(continuity_view.get("generated_at") or "") if continuity_view else ""
    if not view_generated_at and (repo / CONTINUITY_VIEW_PATH).exists():
        try:
            view_generated_at = datetime.fromtimestamp((repo / CONTINUITY_VIEW_PATH).stat().st_mtime, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        except OSError:
            view_generated_at = ""
    actionable = bool(active or recent or handoff or loaded_items)
    if view_exists:
        age = _age_days(view_generated_at, now=current)
        view_status = _item_status(age)
        loaded_items.append(_loaded_item(source="continuity_view", source_id="markdown", last_updated=view_generated_at, confidence="high", relevance="high", why_loaded="Continuity View available", staleness_status=view_status))
        if age is not None and age > FRESH_MAX_DAYS:
            issues.append(_issue("stale_continuity_view", "warning", CONTINUITY_VIEW_PATH.as_posix(), "Continuity View may be stale.", "Continuity View was generated more than freshness threshold days ago", age_days=age, recommendation="Regenerate the Continuity View after significant work."))
    else:
        severity = "warning" if actionable else "info"
        issues.append(_issue("missing_continuity_view", severity, CONTINUITY_VIEW_PATH.as_posix(), "Continuity View is missing.", "Continuity View markdown has not been generated", recommendation="Run `aictx view --repo .` to generate inspectable continuity."))

    contract = _context_dict(context, "execution_contract")
    validated = _clean_strings(_context_dict(context, "capsule").get("validated"), limit=8)
    carryover_gaps = [gap for gap in _context_list(context, "carryover_gaps") if isinstance(gap, dict)]
    for gap in carryover_gaps:
        if str(gap.get("kind") or "") == "missing_validation":
            issues.append(_issue("missing_validation_evidence", "warning", _RESUME_CONTRACTS_PATH.as_posix(), str(gap.get("summary") or "Validation evidence is missing for carried continuity."), "carryover_gaps contains missing_validation", source_id=str(gap.get("source_execution_id") or ""), related_paths=_clean_strings(gap.get("related_paths"), limit=8), recommendation=str(gap.get("next_action") or gap.get("recommended_command") or "Run or record the expected validation before relying on this continuity.")))
            break
    if contract:
        first_action = contract.get("first_action") if isinstance(contract.get("first_action"), dict) else {}
        test_command = contract.get("test_command") if isinstance(contract.get("test_command"), dict) else {}
        loaded_items.append(_loaded_item(source="execution_contract", source_id=str(contract.get("contract_id") or contract.get("id") or "current"), last_updated=str(contract.get("generated_at") or ""), linked_files=_linked_files(contract), linked_task_or_area=str(contract.get("task_goal") or request_text or ""), confidence="high", relevance="high", why_loaded="current resume execution contract", staleness_status="unverified" if not validated else "fresh"))
        if not first_action or not test_command:
            issues.append(_issue("partial_execution_contract", "warning", _RESUME_CONTRACTS_PATH.as_posix(), "Execution contract is incomplete.", "first_action or test_command is missing", recommendation="Regenerate resume context or inspect contract generation."))
        if not validated and not any(str(gap.get("kind") or "") == "missing_validation" for gap in carryover_gaps):
            issues.append(_issue("pending_validation_for_new_contract", "info", _RESUME_CONTRACTS_PATH.as_posix(), "Execution contract is pending validation.", "freshly generated execution contract has not run yet", recommendation="Run or record the expected validation during finalize."))

    try:
        stale_report = refresh_staleness(repo, now=current, persist=False)  # type: ignore[name-defined]
    except NameError:
        from . import refresh_staleness
        stale_report = refresh_staleness(repo, now=current, persist=False)
    except Exception:
        stale_report = {}

    for item in loaded_items:
        status = str(item.get("staleness_status") or "")
        if status == "demoted":
            issues.append(_issue("old_context_demoted", "info", str(item.get("source") or ""), "Old continuity was demoted to background evidence.", "continuity age is beyond possibly_stale threshold", source_id=str(item.get("source_id") or ""), recommendation="Use as background evidence only unless current repo inspection confirms it."))
        elif status == "obsolete":
            issues.append(_issue("obsolete_context", "warning", str(item.get("source") or ""), "Continuity item appears obsolete.", "continuity age is beyond obsolete threshold", source_id=str(item.get("source_id") or ""), recommendation="Do not treat this item as primary guidance without fresh validation."))

    summary = _summary_counts(loaded_items)
    breakdown = _score_breakdown(issues)
    score = int(breakdown["final_score"])
    status = _status_from(score, issues)
    buckets: dict[str, list[dict[str, Any]]] = {key: [] for key in _STATUSES}
    for item in loaded_items:
        status_key = str(item.get("staleness_status") or "unverified")
        buckets[status_key if status_key in buckets else "unverified"].append(item)
    if not repomap_available:
        buckets["missing"].append({"source": "repomap", "source_id": "index"})
    if not view_exists:
        buckets["missing"].append({"source": "continuity_view", "source_id": "markdown"})
    summary["missing"] = len(buckets["missing"])

    return {
        "score": score,
        "status": status,
        "advisory_only": True,
        "summary": summary,
        "fresh": buckets["fresh"],
        "possibly_stale": buckets["possibly_stale"],
        "stale": buckets["stale"],
        "obsolete": buckets["obsolete"],
        "unverified": buckets["unverified"],
        "demoted": buckets["demoted"],
        "missing": buckets["missing"],
        "issues": issues,
        "loaded_items": loaded_items,
        "scoring_breakdown": breakdown,
        "thresholds": {
            "fresh_max_days": FRESH_MAX_DAYS,
            "possibly_stale_max_days": POSSIBLY_STALE_MAX_DAYS,
            "demoted_max_days": DEMOTED_MAX_DAYS,
        },
        "staleness_report": stale_report,
    }

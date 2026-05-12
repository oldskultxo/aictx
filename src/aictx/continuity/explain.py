from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..runtime_io import slugify
from ..strategy_memory import strategy_reuse_confidence

_KIND_PRIORITY = {"failure": 0, "handoff": 1, "decision": 2, "strategy": 3, "repo_map": 4}
_SOURCE_BY_KIND = {
    "failure": ".aictx/failure_memory/failure_patterns.jsonl",
    "handoff": ".aictx/continuity/handoff.json",
    "decision": ".aictx/continuity/decisions.jsonl",
    "strategy": ".aictx/strategy_memory/strategies.jsonl",
    "repo_map": ".aictx/repo_map/index.json",
}
_MAX_DEFAULTS = {
    "total": 12,
    "failure": 3,
    "handoff": 1,
    "decision": 3,
    "strategy": 2,
    "repo_map": 3,
}


def _clean_string_list(values: Any, *, limit: int = 8) -> list[str]:
    if not isinstance(values, list):
        return []
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = str(value or "").strip().replace("\\", "/")
        if not item or item in seen:
            continue
        cleaned.append(item)
        seen.add(item)
        if len(cleaned) >= limit:
            break
    return cleaned


def _compact_text(*parts: Any, limit: int = 160) -> str:
    for value in parts:
        text = " ".join(str(value or "").strip().split())
        if text:
            return text[: limit - 1].rstrip() + "…" if len(text) > limit else text
    return ""


def _parse_iso(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _staleness_label(value: Any, *, stale: bool = False) -> str:
    if stale:
        return "stale"
    parsed = _parse_iso(value)
    if not parsed:
        return "unknown"
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    age_days = max(0, int((datetime.now(timezone.utc) - parsed).total_seconds() // 86400))
    if age_days <= 7:
        return "fresh"
    if age_days <= 30:
        return "recent"
    if age_days <= 90:
        return "old"
    return "stale"


def _dedupe_paths(repo_root: Path, *groups: Any, limit: int = 8) -> list[str]:
    items: list[str] = []
    for group in groups:
        if isinstance(group, list):
            items.extend(group)
    cleaned: list[str] = []
    seen: set[str] = set()
    for item in items:
        path = str(item or "").strip().replace("\\", "/")
        if not path:
            continue
        try:
            candidate = Path(path)
            if candidate.is_absolute():
                try:
                    path = candidate.relative_to(repo_root).as_posix()
                except ValueError:
                    continue
        except OSError:
            continue
        if path in seen:
            continue
        cleaned.append(path)
        seen.add(path)
        if len(cleaned) >= limit:
            break
    return cleaned


def _reason_path_overlap(paths: list[str], candidates: list[str]) -> list[str]:
    overlaps = [path for path in paths if path in set(candidates)]
    return [f"path_overlap:{path}" for path in overlaps[:2]]


def _reason_decision_paths(paths: list[str], candidates: list[str]) -> list[str]:
    overlaps = [path for path in paths if path in set(candidates)]
    return [f"decision_related_path:{path}" for path in overlaps[:2]]


def _normalize_item(kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": kind,
        "source": str(payload.get("source") or _SOURCE_BY_KIND[kind]),
        "source_id": str(payload.get("source_id") or f"{kind}::{slugify(payload.get('summary') or kind)[:48]}")[:120],
        "summary": _compact_text(payload.get("summary"), limit=160),
        "match_reasons": _clean_string_list(payload.get("match_reasons"), limit=6),
        "confidence": str(payload.get("confidence") or "low"),
        "staleness": str(payload.get("staleness") or "unknown"),
        "related_paths": _clean_string_list(payload.get("related_paths"), limit=6),
        "rank": int(payload.get("rank") or 0),
    }


def _failure_confidence(reasons: list[str], row: dict[str, Any]) -> str:
    strong = 0
    if any(reason.startswith("task_type:") for reason in reasons):
        strong += 1
    if any(reason.startswith("area:") for reason in reasons):
        strong += 1
    if any(reason.startswith("path_overlap:") for reason in reasons):
        strong += 1
    if int(row.get("match_score") or 0) >= 8:
        strong += 1
    if strong >= 2:
        return "high"
    if strong >= 1:
        return "medium"
    return "low"


def _repo_map_confidence(reasons: list[str]) -> str:
    if "repo_map:symbol_match" in reasons or ("repo_map:path_match" in reasons and "repo_map:live_path" in reasons):
        return "high"
    if any(reason in reasons for reason in ("repo_map:path_match", "repo_map:scope_match", "repo_map:test_candidate", "repo_map:entrypoint_candidate")):
        return "medium"
    return "low"


def _strategy_paths(strategy: dict[str, Any]) -> list[str]:
    return _dedupe_paths(
        Path("."),
        strategy.get("entry_points"),
        strategy.get("files_used"),
        strategy.get("files_edited"),
        [strategy.get("primary_entry_point")],
        limit=8,
    )


def _failure_items(
    repo_root: Path,
    *,
    failures: list[dict[str, Any]],
    task_type: str,
    area_id: str,
    candidate_paths: list[str],
    limit: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in failures[:limit]:
        if not isinstance(row, dict):
            continue
        paths = _dedupe_paths(repo_root, row.get("related_paths"), row.get("files_involved"), limit=6)
        reasons: list[str] = []
        if task_type and str(row.get("task_type") or "") == task_type:
            reasons.append(f"task_type:{task_type}")
        if area_id and str(row.get("area_id") or "") == area_id:
            reasons.append(f"area:{area_id}")
        reasons.extend(_reason_path_overlap(paths, candidate_paths))
        if int(row.get("match_score") or 0) > 0:
            reasons.append(f"failure_match_score:{int(row.get('match_score') or 0)}")
        fingerprint = _clean_string_list(row.get("error_fingerprints"), limit=1)
        if fingerprint:
            reasons.append(f"error_fingerprint:{fingerprint[0]}")
        rows.append(_normalize_item("failure", {
            "source": _SOURCE_BY_KIND["failure"],
            "source_id": str(row.get("failure_id") or row.get("signature") or "failure::unknown"),
            "summary": _compact_text(row.get("error_text"), row.get("signature"), row.get("failure_signature"), row.get("resolution_hint")),
            "match_reasons": reasons,
            "confidence": _failure_confidence(reasons, row),
            "staleness": _staleness_label(row.get("timestamp")),
            "related_paths": paths,
        }))
    return rows


def _handoff_items(
    repo_root: Path,
    *,
    handoff: dict[str, Any],
    candidate_paths: list[str],
    limit: int,
) -> list[dict[str, Any]]:
    if not handoff or limit <= 0:
        return []
    paths = _dedupe_paths(repo_root, handoff.get("recommended_starting_points"), limit=6)
    reasons = ["latest_handoff"]
    reasons.extend(_reason_path_overlap(paths, candidate_paths))
    if _clean_string_list(handoff.get("next_steps"), limit=1):
        reasons.append("handoff_has_next_steps")
    elif paths:
        reasons.append("handoff_has_starting_points")
    confidence = "high" if any(reason.startswith("path_overlap:") for reason in reasons) or any(reason.startswith("handoff_has_") for reason in reasons[1:]) else "medium"
    return [_normalize_item("handoff", {
        "source": _SOURCE_BY_KIND["handoff"],
        "source_id": f"handoff::{str(handoff.get('source_execution_id') or handoff.get('updated_at') or 'latest').strip()}",
        "summary": _compact_text(handoff.get("summary"), _clean_string_list(handoff.get("next_steps"), limit=1)[0] if _clean_string_list(handoff.get("next_steps"), limit=1) else ""),
        "match_reasons": reasons,
        "confidence": confidence,
        "staleness": _staleness_label(handoff.get("updated_at")),
        "related_paths": paths,
    })]


def _decision_items(
    repo_root: Path,
    *,
    decisions: list[dict[str, Any]],
    candidate_paths: list[str],
    limit: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in decisions[:limit]:
        if not isinstance(row, dict):
            continue
        paths = _dedupe_paths(repo_root, row.get("related_paths"), limit=6)
        reasons = ["recent_decision"]
        reasons.extend(_reason_decision_paths(paths, candidate_paths))
        subsystem = str(row.get("subsystem") or "").strip()
        if subsystem:
            reasons.append(f"subsystem:{subsystem}")
        confidence = "high" if any(reason.startswith("decision_related_path:") for reason in reasons) else "medium" if subsystem or paths else "low"
        source_id_basis = str(row.get("execution_id") or slugify(str(row.get("decision") or "decision"))[:48] or "decision")
        rows.append(_normalize_item("decision", {
            "source": _SOURCE_BY_KIND["decision"],
            "source_id": f"decision::{source_id_basis}",
            "summary": _compact_text(row.get("decision"), row.get("rationale"), row.get("subsystem")),
            "match_reasons": reasons,
            "confidence": confidence,
            "staleness": _staleness_label(row.get("timestamp")),
            "related_paths": paths,
        }))
    return rows


def _strategy_items(
    repo_root: Path,
    *,
    selected_strategy: dict[str, Any],
    limit: int,
) -> list[dict[str, Any]]:
    if not selected_strategy or limit <= 0:
        return []
    confidence = strategy_reuse_confidence(selected_strategy)
    reasons = [f"strategy_confidence:{confidence}"]
    reasons.extend(_clean_string_list(selected_strategy.get("matched_signals"), limit=4))
    return [_normalize_item("strategy", {
        "source": _SOURCE_BY_KIND["strategy"],
        "source_id": str(selected_strategy.get("task_id") or "strategy"),
        "summary": _compact_text(selected_strategy.get("task_text"), selected_strategy.get("selection_reason")),
        "match_reasons": reasons,
        "confidence": confidence if confidence in {"low", "medium", "high"} else "low",
        "staleness": _staleness_label(selected_strategy.get("timestamp")),
        "related_paths": _dedupe_paths(repo_root, selected_strategy.get("entry_points"), selected_strategy.get("files_used"), selected_strategy.get("files_edited"), [selected_strategy.get("primary_entry_point")], limit=6),
    })]


def _repo_map_items(repo_root: Path, *, repo_map_items: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in repo_map_items[:limit]:
        if not isinstance(row, dict):
            continue
        reasons = _clean_string_list(row.get("reasons"), limit=6)
        if not reasons:
            reason_text = str(row.get("reason") or "").strip()
            reasons = _clean_string_list([item.strip() for item in reason_text.split(",")] if reason_text else [], limit=6)
        paths = _dedupe_paths(repo_root, row.get("paths"), [row.get("path")], limit=6)
        rows.append(_normalize_item("repo_map", {
            "source": _SOURCE_BY_KIND["repo_map"],
            "source_id": str(row.get("id") or row.get("path") or "repo_map"),
            "summary": _compact_text(row.get("title"), row.get("path")),
            "match_reasons": reasons,
            "confidence": _repo_map_confidence(reasons),
            "staleness": "unknown",
            "related_paths": paths,
        }))
    return rows


def build_loaded_context_metadata(
    repo_root: Path,
    *,
    request_text: str,
    task_type: str,
    area_id: str,
    continuity_context: dict[str, Any],
    capsule: dict[str, Any],
    selected_strategy: dict[str, Any] | None = None,
    repo_map_items: list[dict[str, Any]] | None = None,
    first_action_path: str = "",
    full: bool = False,
) -> list[dict[str, Any]]:
    _ = request_text  # explicit additive metadata uses already loaded context; no second retrieval.
    caps = dict(_MAX_DEFAULTS)
    if full:
        caps["failure"] = 4
        caps["decision"] = 4
        caps["repo_map"] = 4
    context = continuity_context if isinstance(continuity_context, dict) else {}
    strategy = selected_strategy if isinstance(selected_strategy, dict) and selected_strategy else (context.get("procedural_reuse") if isinstance(context.get("procedural_reuse"), dict) else {})
    repo_map = [row for row in (repo_map_items or []) if isinstance(row, dict)]
    entry_points = []
    if isinstance(capsule, dict):
        entry_points.extend(str(item.get("path") or "") for item in capsule.get("entry_points", []) if isinstance(item, dict))
        fallback = capsule.get("repo_map") if isinstance(capsule.get("repo_map"), dict) else {}
        entry_points.extend(str(item.get("path") or "") for item in fallback.get("primary", []) + fallback.get("secondary", []) if isinstance(item, dict))
    candidate_paths = _dedupe_paths(repo_root, [first_action_path], entry_points, limit=8)

    items: list[dict[str, Any]] = []
    items.extend(_failure_items(repo_root, failures=context.get("failures", []) if isinstance(context.get("failures"), list) else [], task_type=str(task_type or ""), area_id=str(area_id or ""), candidate_paths=candidate_paths, limit=caps["failure"]))
    items.extend(_handoff_items(repo_root, handoff=context.get("handoff", {}) if isinstance(context.get("handoff"), dict) else {}, candidate_paths=candidate_paths, limit=caps["handoff"]))
    items.extend(_decision_items(repo_root, decisions=context.get("decisions", []) if isinstance(context.get("decisions"), list) else [], candidate_paths=candidate_paths, limit=caps["decision"]))
    items.extend(_strategy_items(repo_root, selected_strategy=strategy if isinstance(strategy, dict) else {}, limit=caps["strategy"]))
    items.extend(_repo_map_items(repo_root, repo_map_items=repo_map, limit=caps["repo_map"]))

    items.sort(key=lambda item: (_KIND_PRIORITY.get(str(item.get("kind") or "repo_map"), 99), -len(item.get("match_reasons", [])), str(item.get("source_id") or "")))
    bounded = items[: caps["total"]]
    for index, item in enumerate(bounded, start=1):
        item["rank"] = index
    return bounded

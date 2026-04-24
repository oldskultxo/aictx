from __future__ import annotations

import json
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
    write_json,
)
from .strategy_memory import load_strategies, select_strategy

HANDOFF_PATH = REPO_CONTINUITY_DIR / "handoff.json"
DECISIONS_PATH = REPO_CONTINUITY_DIR / "decisions.jsonl"
SEMANTIC_REPO_PATH = REPO_CONTINUITY_DIR / "semantic_repo.json"
DEDUPE_REPORT_PATH = REPO_CONTINUITY_DIR / "dedupe_report.json"
STALENESS_PATH = REPO_CONTINUITY_DIR / "staleness.json"
CONTINUITY_METRICS_PATH = REPO_CONTINUITY_DIR / "continuity_metrics.json"


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


def render_continuity_summary(context: dict[str, Any], repo_root: Path) -> str:
    session = context.get("session") if isinstance(context.get("session"), dict) else {}
    loaded = context.get("loaded") if isinstance(context.get("loaded"), dict) else {}
    agent_label, session_count = _session_summary_parts(session, repo_root)
    lines = [
        f"{agent_label} (session #{session_count}) - awake",
        "",
        "Loaded:",
        f"- handoff: {'yes' if loaded.get('handoff') else 'no'}",
        f"- decisions: {'yes' if loaded.get('decisions') else 'no'}",
        f"- failures: {'yes' if loaded.get('failures') else 'no'}",
        f"- preferences: {'yes' if loaded.get('preferences') else 'no'}",
        f"- semantic_repo: {'yes' if loaded.get('semantic_repo') else 'no'}",
        f"- procedural_reuse: {'yes' if loaded.get('procedural_reuse') else 'no'}",
    ]
    return "\n".join(lines)


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
    summary = str(result.get("result_summary") or "").strip()
    if not summary:
        return None
    session = prepared.get("continuity_context", {}).get("session", {}) if isinstance(prepared.get("continuity_context"), dict) else {}
    try:
        source_session = int(session.get("session_count") or 0) if isinstance(session, dict) else 0
    except (TypeError, ValueError):
        source_session = 0
    source_execution_id = str(prepared.get("envelope", {}).get("execution_id") or "") if isinstance(prepared.get("envelope"), dict) else ""
    handoff = {
        "summary": summary,
        "completed": [summary],
        "open_items": [],
        "risks": [],
        "next_steps": [],
        "recommended_starting_points": _observed_files(prepared),
        "updated_at": timestamp,
        "source_session": source_session,
        "source_execution_id": source_execution_id,
    }
    write_json(repo_root / HANDOFF_PATH, handoff)
    return {"path": (repo_root / HANDOFF_PATH).as_posix(), "handoff": handoff}


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
    if bool(cross_memory.get("known_failure_avoidance")):
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
        "warnings": warnings,
    }
    context["continuity_summary_text"] = render_continuity_summary(context, repo_root)
    return context

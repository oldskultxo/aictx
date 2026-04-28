from __future__ import annotations

import argparse
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import core_runtime
from .area_memory import area_hints, derive_area_id, update_area_memory
from .adapters import resolve_adapter_profile
from .continuity import (
    load_continuity_context,
    persist_decision_memory,
    persist_handoff_memory,
    persist_semantic_repo_memory,
    update_continuity_metrics,
    write_last_execution_summary,
)
from .failure_memory import link_resolved_failures, lookup_failures, persist_failure_pattern
from .messages import MESSAGE_MODE_MUTED, MESSAGE_MODE_UNMUTED, messages_muted
from .runtime_capture import SIGNAL_FIELDS, build_capture, normalize_error_events
from .runtime_contract import resolve_effective_preferences, runtime_consistency_report
from .runtime_io import slugify
from .runtime_memory import rank_records
from .runtime_tasks import resolve_observed_task_type, resolve_task_type
from .state import REPO_MEMORY_DIR, REPO_METRICS_DIR, mark_startup_banner_shown, read_json, touch_session_identity, write_json
from .strategy_memory import build_strategy_entry, persist_strategy, select_strategy
from .work_state import compact_work_state_for_prepare, load_active_work_state_checked, merge_work_state_from_execution

EXECUTION_LOG_PATH = REPO_METRICS_DIR / "agent_execution_log.jsonl"
REAL_EXECUTION_LOG_PATH = REPO_METRICS_DIR / "execution_logs.jsonl"
EXECUTION_FEEDBACK_PATH = REPO_METRICS_DIR / "execution_feedback.jsonl"
EXECUTION_STATUS_PATH = REPO_METRICS_DIR / "agent_execution_status.json"
HEURISTIC_SKILL_PATTERN = re.compile(r"(\$[A-Za-z0-9:_-]+|SKILL\.md|\bskill\b)", re.IGNORECASE)


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    path.write_text((payload + "\n") if payload else "", encoding="utf-8")


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def normalize_skill_metadata(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    normalized: dict[str, str] = {}
    for key in ("skill_id", "skill_name", "skill_path", "source"):
        raw = str(value.get(key, "") or "").strip()
        if raw:
            normalized[key] = raw
    return normalized


def heuristic_skill_detection(user_request: str, envelope: dict[str, Any]) -> dict[str, Any]:
    invocation = envelope.get("invocation_context", {}) if isinstance(envelope.get("invocation_context"), dict) else {}
    request = str(user_request or "")
    probable_name = ""
    match = HEURISTIC_SKILL_PATTERN.search(request)
    if match and match.group(0).startswith("$"):
        probable_name = match.group(0).lstrip("$")
    if not probable_name:
        probable_name = str(invocation.get("skill_name", "") or "").strip()
    detected = bool(match or probable_name or invocation.get("skill_path"))
    return {
        "detected": detected,
        "authority": "heuristic" if detected else "none",
        "confidence": "low" if detected else "none",
        "probable_skill_name": probable_name,
    }


def _looks_like_file_path(value: str) -> bool:
    text = str(value or "").strip()
    if not text or "\n" in text or text.startswith("-"):
        return False
    if "/" in text or "\\" in text:
        return True
    suffix = Path(text).suffix
    return bool(suffix and len(suffix) <= 12)


def _repomap_file_hints(capture: dict[str, Any]) -> list[str]:
    hints: list[str] = []
    for key in ("files_opened", "files_edited", "tests_executed"):
        values = capture.get(key, [])
        if not isinstance(values, list):
            continue
        for value in values:
            text = str(value or "").strip().replace("\\", "/")
            if text and _looks_like_file_path(text) and text not in hints:
                hints.append(text)
    return hints


def prepare_repo_map_status(repo_root: Path, capture: dict[str, Any]) -> dict[str, Any]:
    try:
        from .repo_map.config import load_repomap_config
        from .repo_map.refresh import refresh_repo_map

        config = load_repomap_config(repo_root)
        if not bool(config.get("enabled", False)):
            return {
                "enabled": False,
                "available": False,
                "used": False,
                "refresh_status": "disabled",
            }
        result = refresh_repo_map(
            repo_root,
            mode="quick",
            budget_ms=int(config.get("quick_refresh_budget_ms", 300)),
            max_changed_files=int(config.get("quick_refresh_max_files", 20)),
            changed_file_hints=_repomap_file_hints(capture),
        )
        status = str(result.get("status") or "unknown")
        return {
            "enabled": True,
            "available": status not in {"unavailable", "skipped"},
            "used": status not in {"unavailable", "skipped", "needs_full_refresh"},
            "refresh_mode": "quick",
            "refresh_status": status,
            "refresh_ms": int(result.get("duration_ms") or 0),
        }
    except Exception as exc:
        return {
            "enabled": True,
            "available": False,
            "used": False,
            "refresh_mode": "quick",
            "refresh_status": "error",
            "error": type(exc).__name__,
        }


def classify_execution(envelope: dict[str, Any]) -> dict[str, Any]:
    explicit_skill = normalize_skill_metadata(envelope.get("skill_metadata"))
    explicit_mode = str(envelope.get("execution_mode", "") or "").strip().lower()
    if explicit_skill or explicit_mode == "skill":
        return {
            "execution_mode": "skill",
            "skill_metadata": explicit_skill,
            "skill_detection": {
                "detected": True,
                "authority": "explicit",
                "confidence": "high",
                "probable_skill_name": explicit_skill.get("skill_name", ""),
            },
        }
    invocation = envelope.get("invocation_context", {}) if isinstance(envelope.get("invocation_context"), dict) else {}
    invocation_skill = normalize_skill_metadata(invocation.get("skill_metadata", invocation))
    invocation_mode = str(invocation.get("execution_mode", "") or "").strip().lower()
    if invocation_skill or invocation_mode == "skill":
        return {
            "execution_mode": "skill",
            "skill_metadata": invocation_skill,
            "skill_detection": {
                "detected": True,
                "authority": "structured",
                "confidence": "medium",
                "probable_skill_name": invocation_skill.get("skill_name", ""),
            },
        }
    heuristic = heuristic_skill_detection(str(envelope.get("user_request", "") or ""), envelope)
    return {
        "execution_mode": "plain",
        "skill_metadata": {},
        "skill_detection": heuristic,
    }


def should_prepare_packet(user_request: str, execution_mode: str, declared_task_type: str | None = None) -> bool:
    if str(execution_mode or "").strip().lower() == "skill":
        return True
    task_type = str(declared_task_type or "").strip()
    if task_type in {"bug_fixing", "testing", "architecture", "performance"}:
        return True
    lowered = str(user_request or "").lower()
    debug_signals = [
        "debug",
        "failing",
        "failure",
        "error",
        "traceback",
        "exception",
        "assert",
        "test",
        "pytest",
        "coverage",
        "architecture",
        "performance",
        "packet",
    ]
    return any(signal in lowered for signal in debug_signals)


def _clean_list(values: Any, *, limit: int = 0) -> list[str]:
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
        if limit and len(cleaned) >= limit:
            break
    return cleaned


def _packet_repo_scope(hints: dict[str, Any], selected_strategy: dict[str, Any] | None, related_failures: list[dict[str, Any]]) -> list[dict[str, str]]:
    paths: list[str] = []
    if selected_strategy:
        paths.extend(_clean_list(selected_strategy.get("entry_points")))
        paths.extend(_clean_list(selected_strategy.get("files_used")))
    paths.extend(_clean_list(hints.get("related_files")))
    for failure in related_failures:
        if isinstance(failure, dict):
            paths.extend(_clean_list(failure.get("related_paths")))
            paths.extend(_clean_list(failure.get("files_involved")))
    return [{"path": path} for path in _clean_list(paths, limit=12)]


def _packet_path(repo_root: Path, execution_id: str) -> Path:
    safe_id = slugify(execution_id or "execution")[:80] or "execution"
    return repo_root / ".aictx" / "delta" / "last_packets" / f"{safe_id}.json"


def build_context_packet(
    repo_root: Path,
    envelope: dict[str, Any],
    task_resolution: dict[str, Any],
    retrieval_matches: list[dict[str, Any]],
    selected_strategy: dict[str, Any] | None,
    continuity_context: dict[str, Any],
    hints: dict[str, Any],
    related_failures: list[dict[str, Any]],
    communication_policy: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    task_text = str(envelope.get("user_request") or "")
    task_id = str(envelope.get("execution_id") or slugify(task_text)[:80] or "task")
    packet = {
        "version": 1,
        "task": task_text,
        "task_summary": task_text[:240],
        "task_id": task_id,
        "task_type": str(task_resolution.get("task_type") or "unknown"),
        "task_type_resolution": dict(task_resolution),
        "project": repo_root.name,
        "repo_scope": _packet_repo_scope(hints, selected_strategy, related_failures),
        "user_preferences": [],
        "constraints": [],
        "architecture_rules": [],
        "relevant_memory": [
            {
                "id": str(row.get("id") or row.get("title") or ""),
                "title": str(row.get("title") or row.get("id") or ""),
                "summary": str(row.get("summary") or row.get("text") or "")[:500],
                "type": str(row.get("type") or ""),
            }
            for row in retrieval_matches[:5]
            if isinstance(row, dict)
        ],
        "known_patterns": [],
        "fallback_mode": bool(task_resolution.get("fallback")),
        "task_memory": {
            "task_specific_memory_used": bool(selected_strategy),
            "selected_strategy_id": str((selected_strategy or {}).get("task_id") or ""),
            "selection_reason": str((selected_strategy or {}).get("selection_reason") or ""),
        },
        "failure_memory": {
            "failure_memory_used": bool(related_failures),
            "related_failures": related_failures[:5],
        },
        "memory_graph": {
            "graph_used": bool(continuity_context.get("semantic_repo")),
            "seed_count": len(_packet_repo_scope(hints, selected_strategy, related_failures)),
            "expansion_depth_used": 0,
            "graph_hits": 0,
        },
        "telemetry_granularity": {
            "phases": [
                {"phase_name": "prepare_context", "notes": "packet built by prepare_execution"},
                {"phase_name": "execute_task", "notes": "agent/runtime execution"},
                {"phase_name": "finalize_learning", "notes": "finalize_execution telemetry and memory writes"},
            ]
        },
        "context_budget": {"mode": "conservative", "max_repo_scope_items": 12, "max_relevant_memory_items": 5},
        "optimization_report": {"status": "not_run"},
        "communication_policy": communication_policy,
        "strategy_hint": selected_strategy or {},
        "area_hints": hints,
        "relevant_failures": related_failures[:5],
    }
    packet["architecture_decisions"] = list(packet["architecture_rules"])
    packet["relevant_paths"] = list(packet["repo_scope"])
    packet["relevant_patterns"] = list(packet["known_patterns"])
    packet["validation_recipes"] = []
    packet["model_suggestion"] = ""
    try:
        optimized = core_runtime.optimize_packet(packet)
        if isinstance(optimized, dict) and isinstance(optimized.get("packet"), dict):
            packet = optimized["packet"]
            if isinstance(optimized.get("report"), dict):
                packet["optimization_report"] = optimized["report"]
    except Exception as exc:
        packet["optimization_report"] = {"status": "skipped", "reason": str(exc)[:200]}
    path = _packet_path(repo_root, task_id)
    write_json(path, packet)
    return packet, path.as_posix()


def build_execution_envelope(payload: dict[str, Any]) -> dict[str, Any]:
    repo_root = Path(str(payload.get("repo_root") or ".")).expanduser().resolve()
    user_request = str(payload.get("user_request") or payload.get("task") or "").strip()
    agent_id = str(payload.get("agent_id") or payload.get("agent") or payload.get("adapter_id") or "").strip()
    execution_id = str(payload.get("execution_id") or "").strip()
    timestamp = str(payload.get("timestamp") or now_iso()).strip()
    if not user_request:
        raise ValueError("user_request is required")
    if not agent_id:
        raise ValueError("agent_id or adapter_id is required")
    if not execution_id:
        raise ValueError("execution_id is required")
    return {
        "repo_root": repo_root.as_posix(),
        "user_request": user_request,
        "agent_id": agent_id,
        "adapter_id": str(payload.get("adapter_id") or agent_id).strip(),
        "execution_id": execution_id,
        "timestamp": timestamp,
        "declared_task_type": str(payload.get("declared_task_type") or "").strip() or None,
        "execution_mode": str(payload.get("execution_mode") or "").strip().lower() or "plain",
        "skill_metadata": payload.get("skill_metadata", {}),
        "invocation_context": payload.get("invocation_context", {}),
        "session_id": str(payload.get("session_id") or "").strip(),
        "files_opened": [str(item) for item in payload.get("files_opened", []) if str(item).strip()] if isinstance(payload.get("files_opened"), list) else [],
        "files_edited": [str(item) for item in payload.get("files_edited", []) if str(item).strip()] if isinstance(payload.get("files_edited"), list) else [],
        "files_reopened": [str(item) for item in payload.get("files_reopened", []) if str(item).strip()] if isinstance(payload.get("files_reopened"), list) else [],
        "commands_executed": [str(item) for item in payload.get("commands_executed", []) if str(item).strip()] if isinstance(payload.get("commands_executed"), list) else [],
        "tests_executed": [str(item) for item in payload.get("tests_executed", []) if str(item).strip()] if isinstance(payload.get("tests_executed"), list) else [],
        "notable_errors": [str(item) for item in payload.get("notable_errors", []) if str(item).strip()] if isinstance(payload.get("notable_errors"), list) else [],
        "error_events": normalize_error_events(payload.get("error_events", [])),
        "work_state": payload.get("work_state", {}) if isinstance(payload.get("work_state"), dict) else {},
    }


def load_bootstrap_sources(repo_root: Path) -> dict[str, Any]:
    memory_root = repo_root / REPO_MEMORY_DIR
    return {
        "derived_boot_summary": read_json(
            memory_root / "derived_boot_summary.json",
            {
                "version": 1,
                "project": repo_root.name,
                "repo_root": str(repo_root),
                "engine_name": "aictx",
                "bootstrap_required": True,
            },
        ),
        "user_preferences": read_json(
            memory_root / "user_preferences.json",
            {
                "preferred_language": "",
                "communication": {"layer": "disabled", "mode": "caveman_full"},
            },
        ),
        "project_bootstrap": read_json(
            memory_root / "project_bootstrap.json",
            {
                "version": 1,
                "project": repo_root.name,
                "repo_root": str(repo_root),
                "engine_name": "aictx",
            },
        ),
    }


def prepare_execution(payload: dict[str, Any]) -> dict[str, Any]:
    envelope = build_execution_envelope(payload)
    repo_root = Path(envelope["repo_root"])
    message_output_muted = messages_muted(repo_root)
    message_mode = MESSAGE_MODE_MUTED if message_output_muted else MESSAGE_MODE_UNMUTED
    boot_sources = load_bootstrap_sources(repo_root)
    adapter_profile = resolve_adapter_profile(envelope.get("adapter_id"), envelope.get("agent_id"), repo_root=repo_root)
    execution = classify_execution(envelope)
    resolved_preferences = resolve_effective_preferences(repo_root, global_defaults_path=core_runtime.ROOT_PREFS_PATH)
    communication_policy = dict(resolved_preferences.get("effective_preferences", {}).get("communication", {}))
    if not (repo_root / REPO_MEMORY_DIR / "user_preferences.json").exists():
        communication_policy = {"layer": "disabled", "mode": "caveman_full"}
    preferred_language = str(resolved_preferences.get("effective_preferences", {}).get("preferred_language") or "unknown").strip() or "unknown"
    preferred_language_source = str(resolved_preferences.get("sources", {}).get("preferred_language") or "unknown").strip() or "unknown"
    session_identity = touch_session_identity(
        repo_root,
        agent_id=str(envelope.get("agent_id") or ""),
        adapter_id=str(envelope.get("adapter_id") or ""),
        timestamp=str(envelope.get("timestamp") or now_iso()),
        session_id=str((envelope.get("invocation_context") or {}).get("session_id") or envelope.get("session_id") or "") if isinstance(envelope.get("invocation_context"), dict) else str(envelope.get("session_id") or ""),
    )
    capture = build_capture(envelope)
    area_id = derive_area_id(capture["files_opened"] + capture["files_edited"] + capture["tests_executed"])
    task_resolution = resolve_task_type(
        envelope["user_request"],
        explicit_task_type=envelope.get("declared_task_type"),
        touched_files=list(capture.get("files_opened", [])) + list(capture.get("files_edited", [])),
    )
    repo_map_status = prepare_repo_map_status(repo_root, capture)
    retrieval_matches = [
        row for row in rank_records(envelope["user_request"], project=repo_root.name)[:5]
        if row.get("type") != "user_preference"
    ]
    retrieval_summary = {
        "memory_records_considered": len(retrieval_matches),
        "memory_titles": [str(row.get("title") or row.get("id") or "") for row in retrieval_matches[:3]],
        "boot_pref_language": str(boot_sources.get("user_preferences", {}).get("preferred_language", "")),
        "packet_built": False,
        "relevant_memory_count": len(retrieval_matches[:3]),
        "repo_scope_count": 0,
    }
    task_fingerprint = slugify(f"{repo_root.name}:{task_resolution['task_type']}:{envelope['user_request']}")[:80]
    selected_strategy = select_strategy(
        repo_root,
        task_resolution["task_type"],
        files=list(capture.get("files_opened", [])) + list(capture.get("files_edited", [])),
        primary_entry_point=(list(capture.get("files_opened", [])) or [None])[0],
        request_text=envelope["user_request"],
        commands=list(capture.get("commands_executed", [])),
        tests=list(capture.get("tests_executed", [])),
        errors=list(capture.get("notable_errors", [])),
        area_id=area_id,
    )
    continuity_context = load_continuity_context(
        repo_root,
        session_identity=session_identity,
        task_type=task_resolution["task_type"],
        request_text=envelope["user_request"],
        files=list(capture.get("files_opened", [])) + list(capture.get("files_edited", [])),
        primary_entry_point=(list(capture.get("files_opened", [])) or [None])[0],
        commands=list(capture.get("commands_executed", [])),
        tests=list(capture.get("tests_executed", [])),
        errors=list(capture.get("notable_errors", [])),
        area_id=area_id,
    )
    active_work_state_checked = load_active_work_state_checked(repo_root)
    active_work_state_payload = active_work_state_checked.get("active_work_state", {})
    work_state_git_status = active_work_state_checked.get("work_state_git_status", {})
    skipped_work_state = active_work_state_checked.get("skipped_work_state", {})
    explicit_work_state = envelope.get("work_state") if isinstance(envelope.get("work_state"), dict) else {}
    active_work_state = compact_work_state_for_prepare({**active_work_state_payload, **explicit_work_state}) if active_work_state_payload or explicit_work_state else {}
    if active_work_state:
        continuity_context["active_work_state"] = active_work_state
        loaded = continuity_context.get("loaded") if isinstance(continuity_context.get("loaded"), dict) else {}
        loaded["work_state"] = True
        continuity_context["loaded"] = loaded
    elif skipped_work_state:
        continuity_context["skipped_work_state"] = skipped_work_state
        loaded = continuity_context.get("loaded") if isinstance(continuity_context.get("loaded"), dict) else {}
        loaded["work_state"] = False
        continuity_context["loaded"] = loaded
    related_failures = list(continuity_context.get("failures", []))
    hints = area_hints(repo_root, area_id)
    session = continuity_context.get("session", {}) if isinstance(continuity_context.get("session"), dict) else {}
    session_id = str(session.get("session_id") or "")
    banner_text = str(continuity_context.get("startup_banner_text") or "").strip()
    banner_already_shown = bool(session_id and str(session.get("banner_shown_session_id") or "") == session_id)
    startup_banner_text = "" if banner_already_shown else (banner_text or _fallback_startup_banner_text(repo_root, session))
    banner_required = bool(startup_banner_text)
    if message_output_muted:
        startup_banner_text = ""
        banner_required = False
    packet: dict[str, Any] = {}
    packet_path = ""
    if should_prepare_packet(envelope["user_request"], envelope["execution_mode"], task_resolution["task_type"]):
        packet, packet_path = build_context_packet(
            repo_root,
            envelope,
            task_resolution,
            retrieval_matches,
            selected_strategy,
            continuity_context,
            hints,
            [row for row in related_failures if isinstance(row, dict)],
            communication_policy,
        )
        retrieval_summary["packet_built"] = True
        retrieval_summary["repo_scope_count"] = len(packet.get("repo_scope", [])) if isinstance(packet.get("repo_scope"), list) else 0
    telemetry_targets = {
        "execution_log": (repo_root / EXECUTION_LOG_PATH).as_posix(),
        "execution_logs": (repo_root / REAL_EXECUTION_LOG_PATH).as_posix(),
        "execution_feedback": (repo_root / EXECUTION_FEEDBACK_PATH).as_posix(),
        "execution_status": (repo_root / EXECUTION_STATUS_PATH).as_posix(),
        "weekly_summary": (repo_root / REPO_METRICS_DIR / "weekly_summary.json").as_posix(),
    }
    prepared = {
        "envelope": envelope,
        "execution_mode": execution["execution_mode"],
        "skill_metadata": execution["skill_metadata"],
        "skill_detection": execution["skill_detection"],
        "resolved_task_type": task_resolution["task_type"],
        "prepared_task_type": task_resolution["task_type"],
        "task_resolution": task_resolution,
        "task_fingerprint": task_fingerprint,
        "execution_signal_capture": capture,
        "repo_map_status": repo_map_status,
        "area_id": area_id,
        "prepared_area_id": area_id,
        "area_hints": hints,
        "related_failures": related_failures,
        "communication_policy": communication_policy,
        "communication_sources": resolved_preferences.get("sources", {}).get("communication", {}),
        "preferred_language": preferred_language,
        "preferred_language_source": preferred_language_source,
        "effective_preferences": resolved_preferences.get("effective_preferences", {}),
        "consistency_checks": runtime_consistency_report(repo_root, global_defaults_path=core_runtime.ROOT_PREFS_PATH),
        "adapter_profile": adapter_profile,
        "boot_sources": {
            "derived_boot_summary": boot_sources.get("derived_boot_summary", {}),
            "project_bootstrap": boot_sources.get("project_bootstrap", {}),
            "user_preferences": boot_sources.get("user_preferences", {}),
        },
        "packet_path": packet_path,
        "packet": packet,
        "continuity_context": continuity_context,
        "active_work_state": active_work_state,
        "continuity_brief": continuity_context.get("continuity_brief", {}) if isinstance(continuity_context.get("continuity_brief"), dict) else {},
        "agent_label": str(session.get("agent_label") or ""),
        "session_count": int(session.get("session_count") or 0),
        "startup_banner_text": startup_banner_text,
        "startup_banner_policy": {
            "show_in_first_user_visible_response": banner_required,
            "show_once_per_session": True,
            "required": banner_required,
            "already_shown": banner_already_shown,
            "session_id": session_id,
            "position": "response_prefix",
            "text": startup_banner_text,
            "render_in_user_language": True,
            "target_language": "current_user_language",
            "fallback_language": preferred_language,
            "fallback_language_source": preferred_language_source,
            "allow_enrichment": False,
            "allow_language_adaptation": True,
            "allow_fact_enrichment": False,
            "allow_structure_changes": False,
            "preserve_facts": True,
            "do_not_invent": True,
            "preserve_technical_tokens": True,
            "muted": message_output_muted,
            "instruction": "Render this startup banner in the current user language. You may translate or adapt labels and connective wording only. Do not add, remove, reorder, reinterpret, or enrich facts. Do not translate file paths, commands, flags, package names, test names, code identifiers, or other technical tokens. Keep the same compact structure.",
        },
        "message_visibility": {
            "mode": message_mode,
            "startup_banner_suppressed": message_output_muted,
            "agent_summary_suppressed": message_output_muted,
        },
        "continuity_summary_text": str(continuity_context.get("continuity_summary_text") or ""),
        "runtime_text_policy": {
            "translate_to_user_language": True,
            "target_language": "current_user_language",
            "fallback_language": preferred_language,
            "fallback_language_source": preferred_language_source,
            "allow_enrichment": True,
            "preserve_facts": True,
            "do_not_invent": True,
            "keep_compact_by_default": True,
            "instruction": "Runtime-originated user-visible text should be presented in the language currently used with the user. Preserve all real facts from AICTX. Enrichment is allowed only when it adds clarity without inventing information.",
        },
        "retrieval_summary": retrieval_summary,
        "telemetry_targets": telemetry_targets,
        "prepared_at": now_iso(),
        "execution_observation": {
            "task_id": envelope["execution_id"],
            "timestamp": now_iso(),
            "start_time_ms": int(time.time() * 1000),
            "task_type": task_resolution["task_type"],
            "files_opened": list(capture.get("files_opened", [])),
            "files_edited": list(capture.get("files_edited", [])),
            "files_reopened": list(capture.get("files_reopened", [])),
            "commands_executed": list(capture.get("commands_executed", [])),
            "tests_executed": list(capture.get("tests_executed", [])),
            "notable_errors": list(capture.get("notable_errors", [])),
            "error_events": list(capture.get("error_events", [])),
            "capture_provenance": dict(capture.get("provenance", {})),
            "area_id": area_id,
            "execution_time_ms": None,
            "success": None,
            "used_packet": bool(packet),
            "used_strategy": bool(selected_strategy),
        },
    }
    if work_state_git_status:
        prepared["work_state_git_status"] = work_state_git_status
    if skipped_work_state:
        prepared["skipped_work_state"] = skipped_work_state
    if selected_strategy:
        prepared["execution_hint"] = {
            "entry_points": list(selected_strategy.get("entry_points", [])) if isinstance(selected_strategy.get("entry_points"), list) else [],
            "primary_entry_point": str(selected_strategy.get("primary_entry_point") or "") or None,
            "files_used": list(selected_strategy.get("files_used", [])) if isinstance(selected_strategy.get("files_used"), list) else [],
            "based_on": "previous_successful_execution",
            "selection_reason": str(selected_strategy.get("selection_reason") or "recency"),
            "matched_signals": list(selected_strategy.get("matched_signals", [])) if isinstance(selected_strategy.get("matched_signals"), list) else [],
            "similarity_breakdown": dict(selected_strategy.get("similarity_breakdown", {})) if isinstance(selected_strategy.get("similarity_breakdown"), dict) else {},
            "overlapping_files": list(selected_strategy.get("overlapping_files", [])) if isinstance(selected_strategy.get("overlapping_files"), list) else [],
            "related_commands": list(selected_strategy.get("related_commands", [])) if isinstance(selected_strategy.get("related_commands"), list) else [],
            "related_tests": list(selected_strategy.get("related_tests", [])) if isinstance(selected_strategy.get("related_tests"), list) else [],
            "reuse_confidence": str(selected_strategy.get("reuse_confidence") or "low"),
        }
    if execution["execution_mode"] == "skill":
        prepared["skill_context"] = {
            "skill_id": execution["skill_metadata"].get("skill_id", ""),
            "skill_name": execution["skill_metadata"].get("skill_name", ""),
            "skill_path": execution["skill_metadata"].get("skill_path", ""),
            "source": execution["skill_metadata"].get("source", ""),
        }
    elif execution["skill_detection"].get("authority") == "heuristic":
        prepared["skill_context"] = {
            "probable_skill_name": execution["skill_detection"].get("probable_skill_name", ""),
        }
    return prepared


def _fallback_startup_banner_text(repo_root: Path, session: dict[str, Any]) -> str:
    runtime = str(session.get("runtime") or "agent").strip() or "agent"
    repo_id = str(session.get("repo_id") or repo_root.name).strip() or repo_root.name
    agent_label = str(session.get("agent_label") or f"{runtime}@{repo_id}").strip() or f"{runtime}@{repo_id}"
    try:
        session_count = int(session.get("session_count") or 0)
    except (TypeError, ValueError):
        session_count = 0
    return f"{agent_label} · session #{max(session_count, 0)} · awake"


def _final_area_id(prepared: dict[str, Any], observation: dict[str, Any]) -> str:
    observed_paths: list[str] = []
    for key in ("files_opened", "files_edited", "tests_executed"):
        value = observation.get(key)
        if isinstance(value, list):
            observed_paths.extend(str(item) for item in value if str(item).strip())
    derived = derive_area_id(observed_paths)
    if derived and derived != "unknown":
        return derived
    return str(observation.get("area_id") or prepared.get("prepared_area_id") or prepared.get("area_id") or "unknown")


def _final_task_resolution(prepared: dict[str, Any], observation: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    files_opened = list(observation.get("files_opened", [])) if isinstance(observation.get("files_opened"), list) else []
    files_edited = list(observation.get("files_edited", [])) if isinstance(observation.get("files_edited"), list) else []
    return resolve_observed_task_type(
        str(prepared.get("envelope", {}).get("user_request") or ""),
        explicit_task_type=prepared.get("envelope", {}).get("declared_task_type"),
        touched_files=files_opened + files_edited,
        tests_executed=list(observation.get("tests_executed", [])) if isinstance(observation.get("tests_executed"), list) else [],
        commands_executed=list(observation.get("commands_executed", [])) if isinstance(observation.get("commands_executed"), list) else [],
        notable_errors=list(observation.get("notable_errors", [])) if isinstance(observation.get("notable_errors"), list) else [],
        result_summary=str(result.get("result_summary") or ""),
    )


def _effective_task_type(prepared: dict[str, Any], final_task_resolution: dict[str, Any]) -> str:
    final_type = str(final_task_resolution.get("task_type") or "").strip()
    if final_type and final_type != "unknown":
        return final_type
    return str(prepared.get("prepared_task_type") or prepared.get("resolved_task_type") or "unknown")


def append_execution_telemetry(repo_root: Path, prepared: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    log_path = repo_root / EXECUTION_LOG_PATH
    real_log_path = repo_root / REAL_EXECUTION_LOG_PATH
    status_path = repo_root / EXECUTION_STATUS_PATH
    weekly_path = repo_root / REPO_METRICS_DIR / "weekly_summary.json"
    rows = read_jsonl(log_path)
    existing_same = [row for row in rows if row.get("task_fingerprint") == prepared.get("task_fingerprint")]
    prior_total = len(existing_same)
    observation = prepared.get("execution_observation", {}) if isinstance(prepared.get("execution_observation"), dict) else {}
    final_task_resolution = _final_task_resolution(prepared, observation, result)
    final_area_id = _final_area_id(prepared, observation)
    effective_task_type = _effective_task_type(prepared, final_task_resolution)
    effective_area_id = final_area_id if final_area_id != "unknown" else str(prepared.get("prepared_area_id") or prepared.get("area_id") or "unknown")
    prepared["final_task_resolution"] = final_task_resolution
    prepared["final_task_type"] = str(final_task_resolution.get("task_type") or "unknown")
    prepared["final_area_id"] = final_area_id
    prepared["effective_task_type"] = effective_task_type
    prepared["effective_area_id"] = effective_area_id
    used_packet = bool(observation.get("used_packet")) or bool(prepared.get("retrieval_summary", {}).get("packet_built"))
    started_ms = observation.get("start_time_ms")
    finished_ms = int(time.time() * 1000)
    execution_time_ms = max(0, finished_ms - started_ms) if isinstance(started_ms, int) else None
    entry = {
        "execution_id": prepared["envelope"]["execution_id"],
        "agent_id": prepared["envelope"]["agent_id"],
        "execution_mode": prepared["execution_mode"],
        "resolved_task_type": effective_task_type,
        "prepared_task_type": str(prepared.get("prepared_task_type") or prepared.get("resolved_task_type") or "unknown"),
        "final_task_type": str(final_task_resolution.get("task_type") or "unknown"),
        "task_fingerprint": prepared.get("task_fingerprint", ""),
        "success": bool(result.get("success")),
        "validated_learning": bool(result.get("validated_learning")),
        "result_summary": str(result.get("result_summary", "") or ""),
        "execution_time_ms": execution_time_ms,
        "used_strategy": bool(observation.get("used_strategy")),
        "used_packet": used_packet,
        "repeated_context_request": prior_total > 0,
        "recorded_at": now_iso(),
    }
    real_entry = {
        "task_id": str(observation.get("task_id") or prepared["envelope"]["execution_id"]),
        "timestamp": str(observation.get("timestamp") or prepared.get("prepared_at") or now_iso()),
        "task_type": effective_task_type,
        "prepared_task_type": str(prepared.get("prepared_task_type") or prepared.get("resolved_task_type") or "unknown"),
        "final_task_type": str(final_task_resolution.get("task_type") or "unknown"),
        "files_opened": list(observation.get("files_opened", [])) if isinstance(observation.get("files_opened"), list) else [],
        "files_edited": list(observation.get("files_edited", [])) if isinstance(observation.get("files_edited"), list) else [],
        "files_reopened": list(observation.get("files_reopened", [])) if isinstance(observation.get("files_reopened"), list) else [],
        "commands_executed": list(observation.get("commands_executed", [])) if isinstance(observation.get("commands_executed"), list) else [],
        "tests_executed": list(observation.get("tests_executed", [])) if isinstance(observation.get("tests_executed"), list) else [],
        "notable_errors": list(observation.get("notable_errors", [])) if isinstance(observation.get("notable_errors"), list) else [],
        "error_events": list(observation.get("error_events", [])) if isinstance(observation.get("error_events"), list) else [],
        "capture_provenance": dict(observation.get("capture_provenance", {})) if isinstance(observation.get("capture_provenance"), dict) else {},
        "area_id": effective_area_id,
        "prepared_area_id": str(prepared.get("prepared_area_id") or prepared.get("area_id") or "unknown"),
        "final_area_id": final_area_id,
        "execution_time_ms": execution_time_ms,
        "success": bool(result.get("success")),
        "used_packet": used_packet,
    }
    rows.append(entry)
    write_jsonl(log_path, rows)
    append_jsonl(real_log_path, real_entry)
    prepared["last_execution_log"] = real_entry
    write_json(
        status_path,
        {
            "version": 2,
            "executions_total": len(rows),
            "last_execution_id": prepared["envelope"]["execution_id"],
            "last_execution_mode": prepared["execution_mode"],
            "last_success": bool(result.get("success")),
            "last_recorded_at": entry["recorded_at"],
            "last_execution_time_ms": execution_time_ms,
            "real_execution_log": real_log_path.as_posix(),
        },
    )
    weekly = read_json(weekly_path, {"version": 3, "tasks_sampled": 0, "repeated_tasks": 0})
    weekly["tasks_sampled"] = int(weekly.get("tasks_sampled", 0) or 0) + 1
    weekly["repeated_tasks"] = int(weekly.get("repeated_tasks", 0) or 0) + (1 if prior_total else 0)
    weekly["last_execution_id"] = prepared["envelope"]["execution_id"]
    weekly["last_execution_success"] = bool(result.get("success"))
    weekly["last_execution_time_ms"] = execution_time_ms
    weekly["value_evidence"] = {
        "last_task_fingerprint": prepared.get("task_fingerprint", ""),
        "last_execution_time_ms": execution_time_ms,
        "last_used_packet": used_packet,
        "files_opened": real_entry["files_opened"],
        "files_edited": real_entry["files_edited"],
        "files_reopened": real_entry["files_reopened"],
        "commands_executed": real_entry["commands_executed"],
        "tests_executed": real_entry["tests_executed"],
        "repeated_tasks_observed": weekly["repeated_tasks"],
    }
    write_json(weekly_path, weekly)
    return entry


def persist_validated_learning(repo_root: Path, prepared: dict[str, Any], result: dict[str, Any]) -> dict[str, Any] | None:
    if not result.get("success") or not result.get("validated_learning"):
        return None
    summary = str(result.get("result_summary") or "").strip()
    if not summary:
        return None
    learning = {
        "id": f"execution_learning::{prepared['envelope']['execution_id']}",
        "title": prepared["envelope"]["user_request"][:80],
        "summary": summary,
        "task_type": str(prepared.get("effective_task_type") or prepared.get("resolved_task_type") or "unknown"),
        "execution_mode": prepared["execution_mode"],
        "created_at": now_iso(),
        "skill_metadata": prepared.get("skill_metadata", {}) if prepared["execution_mode"] == "skill" else {},
    }
    path = repo_root / REPO_MEMORY_DIR / "workflow_learnings.jsonl"
    rows = read_jsonl(path)
    rows.append(learning)
    write_jsonl(path, rows)
    return {"path": path.as_posix(), "record_id": learning["id"]}


def persist_strategy_memory(repo_root: Path, prepared: dict[str, Any], result: dict[str, Any]) -> dict[str, Any] | None:
    execution_log = prepared.get("last_execution_log", {}) if isinstance(prepared.get("last_execution_log"), dict) else {}
    if not execution_log:
        return None
    if result.get("success") and not result.get("validated_learning"):
        return None
    is_failure = not bool(result.get("success"))
    strategy = build_strategy_entry(prepared, execution_log, timestamp=now_iso(), is_failure=is_failure)
    if not strategy.get("task_id"):
        return None
    return persist_strategy(repo_root, strategy)


def build_aictx_feedback(prepared: dict[str, Any], telemetry_entry: dict[str, Any]) -> dict[str, Any]:
    execution_log = prepared.get("last_execution_log", {}) if isinstance(prepared.get("last_execution_log"), dict) else {}
    files_opened = list(execution_log.get("files_opened", [])) if isinstance(execution_log.get("files_opened"), list) else []
    files_reopened = list(execution_log.get("files_reopened", [])) if isinstance(execution_log.get("files_reopened"), list) else []
    tests_executed = list(execution_log.get("tests_executed", [])) if isinstance(execution_log.get("tests_executed"), list) else []
    commands_executed = list(execution_log.get("commands_executed", [])) if isinstance(execution_log.get("commands_executed"), list) else []
    used_strategy = bool(prepared.get("execution_hint")) or bool(telemetry_entry.get("used_strategy"))
    used_packet = bool(execution_log.get("used_packet")) or bool(prepared.get("retrieval_summary", {}).get("packet_built"))
    files_opened_count = len(files_opened)
    files_reopened_count = len(files_reopened)
    return {
        "files_opened": files_opened_count,
        "reopened_files": files_reopened_count,
        "used_strategy": used_strategy,
        "used_packet": used_packet,
        "possible_redundant_exploration": bool(files_reopened_count > 2 or files_opened_count > 8),
        "previous_strategy_reused": used_strategy,
        "commands_observed": len(commands_executed),
        "tests_observed": len(tests_executed),
    }


def build_capture_quality(execution_log: dict[str, Any]) -> dict[str, Any]:
    provenance = execution_log.get("capture_provenance") if isinstance(execution_log.get("capture_provenance"), dict) else {}
    fields = ["files_opened", "files_edited", "commands_executed", "tests_executed", "notable_errors", "error_events"]
    covered = [
        field
        for field in fields
        if isinstance(execution_log.get(field), list)
        and bool(execution_log.get(field))
        and str(provenance.get(field) or "unknown") != "unknown"
    ]
    unknown = [field for field in fields if str(provenance.get(field) or "unknown") == "unknown"]
    return {
        "covered_fields": covered,
        "unknown_fields": unknown,
        "coverage_ratio": round(len(covered) / len(fields), 4),
        "provenance": dict(provenance),
    }


def build_continuity_value(
    prepared: dict[str, Any],
    execution_log: dict[str, Any],
    handoff_stored: bool,
    decision_stored: bool,
    failure_recorded: bool,
) -> dict[str, Any]:
    continuity = prepared.get("continuity_context", {}) if isinstance(prepared.get("continuity_context"), dict) else {}
    loaded = continuity.get("loaded", {}) if isinstance(continuity.get("loaded"), dict) else {}
    ranked_items = continuity.get("ranked_items", []) if isinstance(continuity.get("ranked_items"), list) else []
    brief = continuity.get("continuity_brief", {}) if isinstance(continuity.get("continuity_brief"), dict) else {}
    useful_loads = [key for key, value in loaded.items() if key != "session" and bool(value)]
    observed_fields = [
        field
        for field in ("files_opened", "files_edited", "commands_executed", "tests_executed", "notable_errors")
        if isinstance(execution_log.get(field), list) and bool(execution_log.get(field))
    ]
    return {
        "loaded_sources": useful_loads,
        "ranked_item_count": len(ranked_items),
        "top_ranked_kind": str(ranked_items[0].get("kind") or "") if ranked_items and isinstance(ranked_items[0], dict) else "",
        "stored_sources": [
            label
            for label, stored in (
                ("handoff", handoff_stored),
                ("decision", decision_stored),
                ("failure", failure_recorded),
            )
            if stored
        ],
        "observed_fields": observed_fields,
        "brief_available": bool(brief),
        "probable_path_count": len(brief.get("probable_paths", [])) if isinstance(brief.get("probable_paths"), list) else 0,
    }


def persist_execution_feedback(repo_root: Path, prepared: dict[str, Any], feedback: dict[str, Any], agent_summary: dict[str, Any] | None = None) -> dict[str, Any]:
    path = repo_root / EXECUTION_FEEDBACK_PATH
    payload = {
        "task_id": str(prepared.get("execution_observation", {}).get("task_id") or prepared.get("envelope", {}).get("execution_id") or ""),
        "execution_id": str(prepared.get("envelope", {}).get("execution_id") or ""),
        "timestamp": now_iso(),
        "aictx_feedback": feedback,
    }
    if agent_summary:
        payload["agent_summary"] = agent_summary
    append_jsonl(path, payload)
    return payload


def _compact_list(values: Any, *, limit: int = 3) -> list[str]:
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


def _humanize_selection_reason(reason: str, *, limit: int = 2) -> list[str]:
    cleaned = str(reason or "").strip()
    if not cleaned:
        return []
    parts: list[str] = []
    for raw in cleaned.split(";"):
        item = raw.strip()
        if not item:
            continue
        if item == "previous_successful_execution":
            parts.append("venía de una ejecución previa con éxito")
        elif item == "recency":
            parts.append("era la referencia más reciente")
        elif item.startswith("task_type:"):
            parts.append(f"coincidía el tipo de tarea ({item.split(':', 1)[1]})")
        elif item.startswith("primary_entry_point:"):
            parts.append(f"apuntaba al mismo punto de entrada ({item.split(':', 1)[1]})")
        elif item.startswith("file_overlap:"):
            parts.append(f"tocaba el mismo archivo ({item.split(':', 1)[1]})")
        elif item.startswith("area:"):
            parts.append(f"coincidía el área ({item.split(':', 1)[1]})")
        elif item.startswith("execution_evidence:"):
            parts.append(f"tenía evidencia real de uso ({item.split(':', 1)[1]})")
        else:
            parts.append(item.replace("_", " "))
        if len(parts) >= limit:
            break
    return parts


def _strategy_summary(summary: dict[str, Any]) -> str:
    points = _compact_list(summary.get("strategy_entry_points"), limit=2)
    reasons = _humanize_selection_reason(str(summary.get("selection_reason") or ""), limit=2)
    if points and reasons:
        return f"reusó la estrategia de {', '.join(points)} porque {', '.join(reasons)}"
    if points:
        return f"reusó la estrategia de {', '.join(points)}"
    if reasons:
        return f"reusó estrategia porque {', '.join(reasons)}"
    if summary.get("strategy_reused"):
        return "reusó una estrategia previa con éxito"
    return ""


def _aictx_value_summary(summary: dict[str, Any]) -> str:
    continuity_value = summary.get("continuity_value") if isinstance(summary.get("continuity_value"), dict) else {}
    loaded_sources = _compact_list(continuity_value.get("loaded_sources"), limit=3)
    repo_map = summary.get("repo_map_status") if isinstance(summary.get("repo_map_status"), dict) else {}
    value_parts: list[str] = []
    if loaded_sources:
        value_parts.append("aictx aportó " + ", ".join(loaded_sources))
    if repo_map.get("used"):
        mode = str(repo_map.get("refresh_mode") or "quick").strip()
        status = str(repo_map.get("refresh_status") or "ok").strip()
        value_parts.append(f"usó RepoMap ({mode}, {status})")
    return "; ".join(value_parts)


def _classification_summary(summary: dict[str, Any]) -> str:
    prepared_task = str(summary.get("prepared_task_type") or "unknown")
    final_task = str(summary.get("effective_task_type") or summary.get("final_task_type") or "unknown")
    prepared_area = str(summary.get("prepared_area_id") or "unknown")
    final_area = str(summary.get("effective_area_id") or summary.get("final_area_id") or "unknown")
    parts: list[str] = []
    if final_task != "unknown" and final_task != prepared_task:
        parts.append(f"clasificación final de tarea: {final_task}")
    if final_area != "unknown" and final_area != prepared_area:
        parts.append(f"área final: {final_area}")
    return "; ".join(parts)


def _continuity_reuse_lines(summary: dict[str, Any]) -> list[str]:
    reused: list[str] = []
    if summary.get("strategy_reused"):
        reason = str(summary.get("selection_reason") or "previous successful execution").strip()
        reused.append(f"strategy: {reason}")
    loaded = summary.get("continuity_loaded") if isinstance(summary.get("continuity_loaded"), dict) else {}
    if loaded.get("handoff"):
        reused.append("handoff")
    if loaded.get("decisions"):
        reused.append("decisions")
    if loaded.get("failures"):
        reused.append("failure context")
    if loaded.get("procedural_reuse") and not summary.get("strategy_reused"):
        reused.append("procedural reuse")
    return reused or ["No prior continuity context was reused"]


def _next_session_guidance(summary: dict[str, Any]) -> str:
    handoff = summary.get("handoff_payload") if isinstance(summary.get("handoff_payload"), dict) else {}
    for key in ("next_steps", "recommended_starting_points", "open_items"):
        values = _compact_list(handoff.get(key), limit=2)
        if values:
            return "; ".join(values)
    text = str(handoff.get("summary") or "").strip()
    return text or "No specific handoff guidance stored"


def _plural(count: int, singular: str, plural: str | None = None) -> str:
    return f"{count} {singular if count == 1 else (plural or singular + 's')}"


def _compact_next_hint(summary: dict[str, Any]) -> str:
    next_guidance = summary.get("next_guidance") if isinstance(summary.get("next_guidance"), dict) else {}
    if not next_guidance:
        return ""
    where = _compact_list(next_guidance.get("where_to_continue"), limit=2)
    if not where:
        where = _compact_list(next_guidance.get("probable_paths"), limit=2)
    if not where:
        return ""
    return "; ".join(where)


def _failure_descriptor(failure: dict[str, Any]) -> str:
    if not isinstance(failure, dict):
        return "fallo"
    code = ""
    codes = failure.get("error_codes")
    if isinstance(codes, list) and codes:
        code = str(codes[0] or "").strip()
    toolchain = ""
    toolchains = failure.get("toolchains")
    if isinstance(toolchains, list) and toolchains:
        toolchain = str(toolchains[0] or "").strip()
    phase = ""
    phases = failure.get("phases")
    if isinstance(phases, list) and phases:
        phase = str(phases[0] or "").strip()
    parts = [part for part in [toolchain, phase, code] if part]
    return " ".join(parts) or str(failure.get("failure_id") or failure.get("signature") or "fallo")


def _failure_descriptors(rows: list[dict[str, Any]], ids: list[str] | None = None, *, limit: int = 2) -> list[str]:
    wanted = set(str(item) for item in (ids or []) if str(item).strip())
    descriptors: list[str] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        row_id = str(row.get("failure_id") or row.get("signature") or "").strip()
        if wanted and row_id not in wanted:
            continue
        descriptor = _failure_descriptor(row)
        if row_id and descriptor == row_id:
            descriptor = row_id
        elif row_id:
            descriptor = f"{descriptor} ({row_id})"
        if descriptor and descriptor not in seen:
            descriptors.append(descriptor)
            seen.add(descriptor)
        if len(descriptors) >= limit:
            break
    missing = [item for item in (ids or []) if str(item).strip() and all(str(item) not in desc for desc in descriptors)]
    for item in missing:
        text = str(item)
        if text not in seen:
            descriptors.append(text)
            seen.add(text)
        if len(descriptors) >= limit:
            break
    return descriptors[:limit]


def render_agent_summary(summary: dict[str, Any]) -> str:
    return render_compact_agent_summary(summary, details_path=".aictx/continuity/last_execution_summary.md")


def render_compact_agent_summary(summary: dict[str, Any], *, details_path: str) -> str:
    files_count = int(summary.get("files_opened", 0) or 0)
    tests_count = len(summary.get("tests_observed", [])) if isinstance(summary.get("tests_observed"), list) else 0
    meaningful_context = any(
        [
            summary.get("strategy_reused"),
            summary.get("handoff_stored"),
            summary.get("decision_stored"),
            summary.get("failure_recorded"),
            summary.get("learning_persisted"),
            summary.get("strategy_persisted"),
        ]
    )
    if not any(
        [
            meaningful_context,
            files_count,
            tests_count,
        ]
    ):
        return f"AICTX summary: esta ejecución no dejó contexto reutilizable, pero quedó registrada. Details: {_render_details_link(details_path)}"
    if not meaningful_context and files_count <= 1 and tests_count == 0:
        return f"AICTX summary: ejecución ligera; no añadió continuidad nueva, pero quedó registrada. Details: {_render_details_link(details_path)}"
    if summary.get("failure_recorded"):
        next_hint = _next_session_guidance(summary)
        failure = summary.get("failure_record") if isinstance(summary.get("failure_record"), dict) else {}
        descriptor = _failure_descriptor(failure)
        if failure.get("existing"):
            return f"AICTX summary: reconoció un patrón de fallo existente ({descriptor}) y actualizó su memoria para no repetirlo. Next recommended focus: {next_hint}. Details: {_render_details_link(details_path)}"
        return f"AICTX summary: aprendió un patrón de fallo nuevo ({descriptor}) para evitar repetirlo. Next recommended focus: {next_hint}. Details: {_render_details_link(details_path)}"
    parts: list[str] = []
    strategy_summary = _strategy_summary(summary)
    if strategy_summary:
        parts.append(strategy_summary)
    value_summary = _aictx_value_summary(summary)
    if value_summary:
        parts.append(value_summary)
    classification_summary = _classification_summary(summary)
    if classification_summary:
        parts.append(classification_summary)
    avoided = _compact_list(summary.get("avoided"), limit=2)
    if avoided:
        if all(str(item).startswith("resolvió ") for item in avoided):
            parts.append("; ".join(avoided))
        else:
            parts.append("evitó " + "; ".join(avoided))
    stored_parts: list[str] = []
    if summary.get("handoff_stored"):
        stored_parts.append("handoff")
    if summary.get("strategy_persisted"):
        stored_parts.append("strategy")
    if summary.get("decision_stored"):
        stored_parts.append("decision")
    if summary.get("learning_persisted"):
        stored_parts.append("validated learning")
    if stored_parts:
        parts.append("guardó " + ", ".join(stored_parts))
    work_state_updated = summary.get("work_state_updated") if isinstance(summary.get("work_state_updated"), dict) else {}
    if work_state_updated.get("updated") and str(work_state_updated.get("task_id") or "").strip():
        parts.append("actualizó work state para " + str(work_state_updated.get("task_id") or "").strip())
    core = "; ".join(parts) if parts else "dejó continuidad útil"
    observed: list[str] = []
    if files_count:
        observed.append(_plural(files_count, "file"))
    if tests_count:
        observed.append(_plural(tests_count, "test"))
    suffixes: list[str] = []
    if observed:
        suffixes.append("observó " + " y ".join(observed))
    next_hint = _compact_next_hint(summary)
    if next_hint:
        suffixes.append(f"siguiente: {next_hint}")
    message = core
    if suffixes:
        message += "; " + "; ".join(suffixes)
    return f"AICTX summary: {message}. Details: {_render_details_link(details_path)}"


def _render_details_link(details_path: str) -> str:
    path = str(details_path or "").strip()
    if not path:
        return ""
    return f"[`{path}`]({path})"


def build_agent_summary(
    prepared: dict[str, Any],
    learning: dict[str, Any] | None,
    strategy: dict[str, Any] | None,
    failure: dict[str, Any] | None,
    *,
    handoff: dict[str, Any] | None = None,
    decisions: list[dict[str, Any]] | None = None,
    resolved_failures: list[str] | None = None,
) -> dict[str, Any]:
    execution_log = prepared.get("last_execution_log", {}) if isinstance(prepared.get("last_execution_log"), dict) else {}
    hint = prepared.get("execution_hint", {}) if isinstance(prepared.get("execution_hint"), dict) else {}
    continuity = prepared.get("continuity_context", {}) if isinstance(prepared.get("continuity_context"), dict) else {}
    loaded = continuity.get("loaded", {}) if isinstance(continuity.get("loaded"), dict) else {}
    prior_failures = continuity.get("failures", []) if isinstance(continuity.get("failures"), list) else []
    avoided: list[str] = []
    if resolved_failures:
        rows = prior_failures or lookup_failures(
            Path(str(prepared.get("envelope", {}).get("repo_root") or ".")).resolve(),
            task_type=str(execution_log.get("task_type") or ""),
            text=str(prepared.get("envelope", {}).get("user_request") or ""),
            files=list(execution_log.get("files_opened", [])) if isinstance(execution_log.get("files_opened"), list) else [],
            area_id=str(execution_log.get("area_id") or ""),
            limit=5,
        )
        descriptors = _failure_descriptors([row for row in rows if isinstance(row, dict)], resolved_failures, limit=2)
        avoided.append("resolvió fallo previo: " + ", ".join(descriptors or [str(item) for item in resolved_failures[:2]]))
    elif prior_failures and not failure:
        descriptors = _failure_descriptors([row for row in prior_failures if isinstance(row, dict)], limit=2)
        if descriptors:
            if execution_log.get("success") is True:
                avoided.append("usó contexto de fallo previo sin repetirlo: " + ", ".join(descriptors))
            else:
                avoided.append("consideró fallo previo relacionado: " + ", ".join(descriptors))
    handoff_payload = handoff.get("handoff", {}) if isinstance(handoff, dict) else {}
    final_task_resolution = prepared.get("final_task_resolution", {}) if isinstance(prepared.get("final_task_resolution"), dict) else {}
    summary = {
        "strategy_reused": bool(hint),
        "selection_reason": str(hint.get("selection_reason") or ""),
        "strategy_entry_points": list(hint.get("entry_points", [])) if isinstance(hint.get("entry_points"), list) else [],
        "prepared_task_type": str(prepared.get("prepared_task_type") or prepared.get("resolved_task_type") or "unknown"),
        "final_task_type": str(prepared.get("final_task_type") or final_task_resolution.get("task_type") or "unknown"),
        "effective_task_type": str(prepared.get("effective_task_type") or prepared.get("resolved_task_type") or "unknown"),
        "prepared_area_id": str(prepared.get("prepared_area_id") or prepared.get("area_id") or "unknown"),
        "final_area_id": str(prepared.get("final_area_id") or execution_log.get("final_area_id") or execution_log.get("area_id") or "unknown"),
        "effective_area_id": str(prepared.get("effective_area_id") or execution_log.get("area_id") or prepared.get("area_id") or "unknown"),
        "final_task_resolution": dict(final_task_resolution),
        "reuse_confidence": str(hint.get("reuse_confidence") or continuity.get("continuity_brief", {}).get("reuse_confidence") or "low"),
        "learning_persisted": bool(learning),
        "strategy_persisted": bool(strategy),
        "failure_recorded": bool(failure),
        "failure_record": dict(failure) if isinstance(failure, dict) else {},
        "resolved_failures": list(resolved_failures or []),
        "failure_context_loaded": bool(prior_failures),
        "handoff_stored": bool(handoff),
        "decision_stored": bool(decisions),
        "continuity_loaded": dict(loaded),
        "handoff_payload": handoff_payload,
        "avoided": avoided,
        "files_opened": len(execution_log.get("files_opened", [])) if isinstance(execution_log.get("files_opened"), list) else 0,
        "files_edited": len(execution_log.get("files_edited", [])) if isinstance(execution_log.get("files_edited"), list) else 0,
        "reopened_files": len(execution_log.get("files_reopened", [])) if isinstance(execution_log.get("files_reopened"), list) else 0,
        "commands_observed": list(execution_log.get("commands_executed", [])) if isinstance(execution_log.get("commands_executed"), list) else [],
        "tests_observed": list(execution_log.get("tests_executed", [])) if isinstance(execution_log.get("tests_executed"), list) else [],
        "error_events_observed": list(execution_log.get("error_events", [])) if isinstance(execution_log.get("error_events"), list) else [],
        "next_guidance": dict(continuity.get("continuity_brief", {})) if isinstance(continuity.get("continuity_brief"), dict) else {},
        "continuity_value": build_continuity_value(prepared, execution_log, bool(handoff), bool(decisions), bool(failure)),
        "capture_quality": build_capture_quality(execution_log),
        "repo_map_status": dict(prepared.get("repo_map_status", {})) if isinstance(prepared.get("repo_map_status"), dict) else {},
        "work_state_updated": dict(prepared.get("work_state_updated", {})) if isinstance(prepared.get("work_state_updated"), dict) else {},
        "active_work_state": dict(continuity.get("active_work_state", {})) if isinstance(continuity.get("active_work_state"), dict) else {},
    }
    return {"structured": summary, "rendered": render_agent_summary(summary)}


def finalize_execution(prepared: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    repo_root = Path(str(prepared.get("envelope", {}).get("repo_root") or ".")).resolve()
    prepared_message_visibility = prepared.get("message_visibility") if isinstance(prepared.get("message_visibility"), dict) else {}
    message_mode = str(prepared_message_visibility.get("mode") or MESSAGE_MODE_UNMUTED)
    message_output_muted = message_mode == MESSAGE_MODE_MUTED
    startup_banner_policy = prepared.get("startup_banner_policy") if isinstance(prepared.get("startup_banner_policy"), dict) else {}
    if prepared.get("startup_banner_text") and not startup_banner_policy.get("already_shown"):
        context = prepared.get("continuity_context") if isinstance(prepared.get("continuity_context"), dict) else {}
        session = context.get("session") if isinstance(context.get("session"), dict) else {}
        mark_startup_banner_shown(
            repo_root,
            session,
            timestamp=str(prepared.get("envelope", {}).get("timestamp") or now_iso()),
        )
    normalized_result = {
        "success": bool(result.get("success")),
        "result_summary": str(result.get("result_summary", "") or ""),
        "validated_learning": bool(result.get("validated_learning")),
        "decisions": list(result.get("decisions", [])) if isinstance(result.get("decisions"), list) else [],
        "semantic_repo": list(result.get("semantic_repo", [])) if isinstance(result.get("semantic_repo"), list) else [],
        "handoff": result.get("handoff", {}) if isinstance(result.get("handoff"), dict) else {},
        "work_state": result.get("work_state", {}) if isinstance(result.get("work_state"), dict) else {},
    }
    telemetry_entry = append_execution_telemetry(repo_root, prepared, normalized_result)
    learning = persist_validated_learning(repo_root, prepared, normalized_result)
    strategy = persist_strategy_memory(repo_root, prepared, normalized_result)
    failure = None
    resolved_failures: list[str] = []
    execution_log = prepared.get("last_execution_log", {}) if isinstance(prepared.get("last_execution_log"), dict) else {}
    if normalized_result["success"]:
        resolved_failures = link_resolved_failures(repo_root, prepared, execution_log)
    else:
        failure = persist_failure_pattern(repo_root, prepared, execution_log, normalized_result)
    update_area_memory(repo_root, execution_log, strategy_stored=bool(strategy), failure_recorded=bool(failure))
    aictx_feedback = build_aictx_feedback(prepared, telemetry_entry)
    finalized_at = now_iso()
    decisions = persist_decision_memory(
        repo_root,
        prepared,
        normalized_result,
        timestamp=finalized_at,
    )
    handoff = persist_handoff_memory(
        repo_root,
        prepared,
        normalized_result,
        timestamp=finalized_at,
        strategy_stored=bool(strategy),
        failure_recorded=bool(failure),
        learning_stored=bool(learning),
    )
    semantic_repo = persist_semantic_repo_memory(
        repo_root,
        prepared,
        normalized_result,
        timestamp=finalized_at,
    )
    continuity_metrics = update_continuity_metrics(repo_root, prepared, telemetry_entry)
    work_state_state = merge_work_state_from_execution(repo_root, prepared, execution_log, normalized_result)
    work_state_updated = None
    if isinstance(work_state_state, dict) and work_state_state:
        task_id = str(work_state_state.get("task_id") or "")
        fields = [
            key for key in ("active_files", "verified", "unverified", "discarded_paths", "uncertainties", "next_action", "recommended_commands", "risks", "source_execution_ids")
            if work_state_state.get(key)
        ]
        work_state_updated = {
            "updated": True,
            "task_id": task_id,
            "path": f".aictx/tasks/threads/{task_id}.json" if task_id else "",
            "fields": fields,
        }
    prepared["work_state_updated"] = work_state_updated
    agent_summary = build_agent_summary(
        prepared,
        learning,
        strategy,
        failure,
        handoff=handoff,
        decisions=decisions,
        resolved_failures=resolved_failures,
    )
    details_summary = write_last_execution_summary(repo_root, agent_summary["structured"])
    details_path = ".aictx/continuity/last_execution_summary.md"
    if isinstance(details_summary, dict):
        resolved_path = str(details_summary.get("path") or "")
        if resolved_path:
            try:
                details_path = Path(resolved_path).relative_to(repo_root).as_posix()
            except ValueError:
                details_path = resolved_path
    agent_summary_text = render_compact_agent_summary(agent_summary["structured"], details_path=details_path)
    returned_agent_summary_text = "" if message_output_muted else agent_summary_text
    persisted_feedback = persist_execution_feedback(repo_root, prepared, aictx_feedback, agent_summary["structured"])
    used_packet = bool(prepared.get("last_execution_log", {}).get("used_packet")) if isinstance(prepared.get("last_execution_log"), dict) else False
    return {
        "execution_id": prepared["envelope"]["execution_id"],
        "execution_mode": prepared["execution_mode"],
        "prepared_task_type": str(prepared.get("prepared_task_type") or prepared.get("resolved_task_type") or "unknown"),
        "final_task_type": str(prepared.get("final_task_type") or "unknown"),
        "effective_task_type": str(prepared.get("effective_task_type") or prepared.get("resolved_task_type") or "unknown"),
        "prepared_area_id": str(prepared.get("prepared_area_id") or prepared.get("area_id") or "unknown"),
        "final_area_id": str(prepared.get("final_area_id") or "unknown"),
        "effective_area_id": str(prepared.get("effective_area_id") or prepared.get("area_id") or "unknown"),
        "final_task_resolution": dict(prepared.get("final_task_resolution", {})) if isinstance(prepared.get("final_task_resolution"), dict) else {},
        "telemetry_entry": telemetry_entry,
        "learning_persisted": learning,
        "strategy_persisted": strategy,
        "failure_persisted": failure,
        "resolved_failures": resolved_failures,
        "aictx_feedback": aictx_feedback,
        "feedback_persisted": persisted_feedback,
        "handoff_persisted": handoff,
        "decisions_persisted": decisions,
        "semantic_repo_persisted": semantic_repo,
        "continuity_metrics_persisted": continuity_metrics,
        "work_state_updated": work_state_updated,
        "agent_summary": agent_summary["structured"],
        "agent_summary_text": returned_agent_summary_text,
        "message_visibility": {
            "mode": message_mode,
            "startup_banner_suppressed": bool(prepared_message_visibility.get("startup_banner_suppressed")),
            "agent_summary_suppressed": message_output_muted,
        },
        "continuity_value": agent_summary["structured"].get("continuity_value", {}),
        "reuse_confidence": agent_summary["structured"].get("reuse_confidence", "low"),
        "capture_quality": agent_summary["structured"].get("capture_quality", {}),
        "agent_summary_policy": {
            "append_to_final_response": True,
            "render_in_user_language": True,
            "target_language": "current_user_language",
            "fallback_language": str(prepared.get("preferred_language") or "unknown"),
            "allow_enrichment": True,
            "preserve_facts": True,
            "do_not_invent": True,
            "instruction": "Append the AICTX final summary in the language currently used with the user. Preserve all factual runtime details. You may enrich slightly for clarity using agent_summary and value_evidence when doing so does not invent facts.",
        },
        "value_evidence": {
            "task_fingerprint": prepared.get("task_fingerprint", ""),
            "repeated_context_request": bool(telemetry_entry.get("repeated_context_request")),
            "execution_time_ms": telemetry_entry.get("execution_time_ms"),
            "used_packet": used_packet,
            "used_strategy": bool(telemetry_entry.get("used_strategy")),
            "files_opened": list(prepared.get("last_execution_log", {}).get("files_opened", [])) if isinstance(prepared.get("last_execution_log", {}).get("files_opened"), list) else [],
            "files_edited": list(prepared.get("last_execution_log", {}).get("files_edited", [])) if isinstance(prepared.get("last_execution_log", {}).get("files_edited"), list) else [],
            "files_reopened": list(prepared.get("last_execution_log", {}).get("files_reopened", [])) if isinstance(prepared.get("last_execution_log", {}).get("files_reopened"), list) else [],
            "commands_executed": list(prepared.get("last_execution_log", {}).get("commands_executed", [])) if isinstance(prepared.get("last_execution_log", {}).get("commands_executed"), list) else [],
            "tests_executed": list(prepared.get("last_execution_log", {}).get("tests_executed", [])) if isinstance(prepared.get("last_execution_log", {}).get("tests_executed"), list) else [],
            "error_events": list(prepared.get("last_execution_log", {}).get("error_events", [])) if isinstance(prepared.get("last_execution_log", {}).get("error_events"), list) else [],
        },
        "finalized_at": finalized_at,
    }


def cli_prepare_execution(args: argparse.Namespace) -> int:
    error_events = _cli_error_events(args)
    payload = {
        "repo_root": args.repo,
        "user_request": args.request,
        "agent_id": args.agent_id,
        "adapter_id": args.adapter_id or args.agent_id,
        "execution_id": args.execution_id,
        "timestamp": args.timestamp or now_iso(),
        "declared_task_type": args.task_type,
        "execution_mode": args.execution_mode or "plain",
        "files_opened": list(args.files_opened or []),
        "files_edited": list(args.files_edited or []),
        "files_reopened": list(args.files_reopened or []),
        "commands_executed": list(args.commands_executed or []),
        "tests_executed": list(args.tests_executed or []),
        "notable_errors": list(args.notable_errors or []),
        "error_events": error_events,
        "work_state": _cli_work_state(args),
        "skill_metadata": {
            "skill_id": args.skill_id,
            "skill_name": args.skill_name,
            "skill_path": args.skill_path,
            "source": args.skill_source,
        },
    }
    print(json.dumps(prepare_execution(payload), indent=2, ensure_ascii=False))
    return 0


def cli_finalize_execution(args: argparse.Namespace) -> int:
    prepared = read_json(Path(args.prepared), {})
    observation = prepared.get("execution_observation", {}) if isinstance(prepared.get("execution_observation"), dict) else {}
    for field in SIGNAL_FIELDS:
        cli_value = _cli_error_events(args) if field == "error_events" else list(getattr(args, field, []) or [])
        observation[field] = cli_value or list(observation.get(field, []) or [])
    prepared["execution_observation"] = observation
    decisions = []
    for raw_decision in list(getattr(args, "decision_json", []) or []):
        try:
            payload = json.loads(raw_decision)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            decisions.append(payload)
    semantic_repo = []
    for raw_semantic in list(getattr(args, "semantic_json", []) or []):
        try:
            payload = json.loads(raw_semantic)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            semantic_repo.append(payload)
    result = {
        "success": bool(args.success),
        "result_summary": args.result_summary,
        "validated_learning": bool(args.validated_learning),
        "decisions": decisions,
        "semantic_repo": semantic_repo,
        "work_state": _cli_work_state(args),
    }
    print(json.dumps(finalize_execution(prepared, result), indent=2, ensure_ascii=False))
    return 0


def _cli_json_dict(raw: str) -> dict[str, Any]:
    text = str(raw or "").strip()
    if not text:
        return {}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _cli_json_file(path: str) -> dict[str, Any]:
    text = str(path or "").strip()
    if not text:
        return {}
    try:
        return _cli_json_dict(Path(text).expanduser().read_text(encoding="utf-8"))
    except OSError:
        return {}


def _cli_work_state(args: argparse.Namespace) -> dict[str, Any]:
    payload = _cli_json_file(getattr(args, "work_state_file", ""))
    payload.update(_cli_json_dict(getattr(args, "work_state_json", "")))
    return payload


def _cli_error_events(args: argparse.Namespace) -> list[dict[str, Any]]:
    raw_values = list(getattr(args, "error_event_json", []) or [])
    events: list[dict[str, Any]] = []
    for raw in raw_values:
        try:
            payload = json.loads(str(raw))
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            events.append(payload)
        elif isinstance(payload, list):
            events.extend(item for item in payload if isinstance(item, dict))
    return normalize_error_events(events)

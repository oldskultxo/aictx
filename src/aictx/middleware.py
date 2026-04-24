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
from .failure_memory import link_resolved_failures, lookup_failures, persist_failure_pattern
from .runtime_capture import SIGNAL_FIELDS, build_capture
from .runtime_contract import resolve_effective_preferences, runtime_consistency_report
from .runtime_io import slugify
from .runtime_memory import rank_records
from .runtime_tasks import resolve_task_type
from .state import REPO_MEMORY_DIR, REPO_METRICS_DIR, read_json, touch_session_identity, write_json
from .strategy_memory import build_strategy_entry, persist_strategy, select_strategy

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
    return False


def build_execution_envelope(payload: dict[str, Any]) -> dict[str, Any]:
    repo_root = Path(str(payload.get("repo_root") or ".")).expanduser().resolve()
    user_request = str(payload.get("user_request") or "").strip()
    agent_id = str(payload.get("agent_id") or payload.get("adapter_id") or "").strip()
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
        "files_opened": [str(item) for item in payload.get("files_opened", []) if str(item).strip()] if isinstance(payload.get("files_opened"), list) else [],
        "files_edited": [str(item) for item in payload.get("files_edited", []) if str(item).strip()] if isinstance(payload.get("files_edited"), list) else [],
        "files_reopened": [str(item) for item in payload.get("files_reopened", []) if str(item).strip()] if isinstance(payload.get("files_reopened"), list) else [],
        "commands_executed": [str(item) for item in payload.get("commands_executed", []) if str(item).strip()] if isinstance(payload.get("commands_executed"), list) else [],
        "tests_executed": [str(item) for item in payload.get("tests_executed", []) if str(item).strip()] if isinstance(payload.get("tests_executed"), list) else [],
        "notable_errors": [str(item) for item in payload.get("notable_errors", []) if str(item).strip()] if isinstance(payload.get("notable_errors"), list) else [],
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
    boot_sources = load_bootstrap_sources(repo_root)
    adapter_profile = resolve_adapter_profile(envelope.get("adapter_id"), envelope.get("agent_id"), repo_root=repo_root)
    execution = classify_execution(envelope)
    resolved_preferences = resolve_effective_preferences(repo_root, global_defaults_path=core_runtime.ROOT_PREFS_PATH)
    communication_policy = dict(resolved_preferences.get("effective_preferences", {}).get("communication", {}))
    if not (repo_root / REPO_MEMORY_DIR / "user_preferences.json").exists():
        communication_policy = {"layer": "disabled", "mode": "caveman_full"}
    session_identity = touch_session_identity(
        repo_root,
        agent_id=str(envelope.get("agent_id") or ""),
        adapter_id=str(envelope.get("adapter_id") or ""),
        timestamp=str(envelope.get("timestamp") or now_iso()),
    )
    capture = build_capture(envelope)
    area_id = derive_area_id(capture["files_opened"] + capture["files_edited"] + capture["tests_executed"])
    task_resolution = resolve_task_type(
        envelope["user_request"],
        explicit_task_type=envelope.get("declared_task_type"),
        touched_files=list(capture.get("files_opened", [])) + list(capture.get("files_edited", [])),
    )
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
    related_failures = lookup_failures(
        repo_root,
        task_type=task_resolution["task_type"],
        text=envelope["user_request"],
        files=list(capture.get("files_opened", [])) + list(capture.get("files_edited", [])),
        area_id=area_id,
    )
    hints = area_hints(repo_root, area_id)
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
        "task_resolution": task_resolution,
        "task_fingerprint": task_fingerprint,
        "execution_signal_capture": capture,
        "area_id": area_id,
        "area_hints": hints,
        "related_failures": related_failures,
        "communication_policy": communication_policy,
        "communication_sources": resolved_preferences.get("sources", {}).get("communication", {}),
        "effective_preferences": resolved_preferences.get("effective_preferences", {}),
        "consistency_checks": runtime_consistency_report(repo_root, global_defaults_path=core_runtime.ROOT_PREFS_PATH),
        "adapter_profile": adapter_profile,
        "boot_sources": {
            "derived_boot_summary": boot_sources.get("derived_boot_summary", {}),
            "project_bootstrap": boot_sources.get("project_bootstrap", {}),
            "user_preferences": boot_sources.get("user_preferences", {}),
        },
        "packet_path": "",
        "packet": {},
        "continuity_context": {
            "session": dict(session_identity.get("session", {})) if isinstance(session_identity.get("session"), dict) else {},
            "warnings": list(session_identity.get("warnings", [])) if isinstance(session_identity.get("warnings"), list) else [],
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
            "capture_provenance": dict(capture.get("provenance", {})),
            "area_id": area_id,
            "execution_time_ms": None,
            "success": None,
            "used_packet": False,
            "used_strategy": bool(selected_strategy),
        },
    }
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


def append_execution_telemetry(repo_root: Path, prepared: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    log_path = repo_root / EXECUTION_LOG_PATH
    real_log_path = repo_root / REAL_EXECUTION_LOG_PATH
    status_path = repo_root / EXECUTION_STATUS_PATH
    weekly_path = repo_root / REPO_METRICS_DIR / "weekly_summary.json"
    rows = read_jsonl(log_path)
    existing_same = [row for row in rows if row.get("task_fingerprint") == prepared.get("task_fingerprint")]
    prior_total = len(existing_same)
    observation = prepared.get("execution_observation", {}) if isinstance(prepared.get("execution_observation"), dict) else {}
    started_ms = observation.get("start_time_ms")
    finished_ms = int(time.time() * 1000)
    execution_time_ms = max(0, finished_ms - started_ms) if isinstance(started_ms, int) else None
    entry = {
        "execution_id": prepared["envelope"]["execution_id"],
        "agent_id": prepared["envelope"]["agent_id"],
        "execution_mode": prepared["execution_mode"],
        "resolved_task_type": prepared["resolved_task_type"],
        "task_fingerprint": prepared.get("task_fingerprint", ""),
        "success": bool(result.get("success")),
        "validated_learning": bool(result.get("validated_learning")),
        "result_summary": str(result.get("result_summary", "") or ""),
        "execution_time_ms": execution_time_ms,
        "used_strategy": bool(observation.get("used_strategy")),
        "repeated_context_request": prior_total > 0,
        "recorded_at": now_iso(),
    }
    real_entry = {
        "task_id": str(observation.get("task_id") or prepared["envelope"]["execution_id"]),
        "timestamp": str(observation.get("timestamp") or prepared.get("prepared_at") or now_iso()),
        "task_type": prepared["resolved_task_type"],
        "files_opened": list(observation.get("files_opened", [])) if isinstance(observation.get("files_opened"), list) else [],
        "files_edited": list(observation.get("files_edited", [])) if isinstance(observation.get("files_edited"), list) else [],
        "files_reopened": list(observation.get("files_reopened", [])) if isinstance(observation.get("files_reopened"), list) else [],
        "commands_executed": list(observation.get("commands_executed", [])) if isinstance(observation.get("commands_executed"), list) else [],
        "tests_executed": list(observation.get("tests_executed", [])) if isinstance(observation.get("tests_executed"), list) else [],
        "notable_errors": list(observation.get("notable_errors", [])) if isinstance(observation.get("notable_errors"), list) else [],
        "capture_provenance": dict(observation.get("capture_provenance", {})) if isinstance(observation.get("capture_provenance"), dict) else {},
        "area_id": str(observation.get("area_id") or prepared.get("area_id") or "unknown"),
        "execution_time_ms": execution_time_ms,
        "success": bool(result.get("success")),
        "used_packet": False,
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
        "last_used_packet": False,
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
        "task_type": prepared["resolved_task_type"],
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
    files_opened_count = len(files_opened)
    files_reopened_count = len(files_reopened)
    return {
        "files_opened": files_opened_count,
        "reopened_files": files_reopened_count,
        "used_strategy": used_strategy,
        "used_packet": False,
        "possible_redundant_exploration": bool(files_reopened_count > 2 or files_opened_count > 8),
        "previous_strategy_reused": used_strategy,
        "commands_observed": len(commands_executed),
        "tests_observed": len(tests_executed),
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


def render_agent_summary(summary: dict[str, Any]) -> str:
    lines = ["AICTX"]
    lines.append(f"- Reused strategy: {'yes' if summary.get('strategy_reused') else 'no'}")
    if summary.get("selection_reason"):
        lines.append(f"- Why: {summary['selection_reason']}")
    lines.append(f"- New learning stored: {'yes' if summary.get('learning_persisted') else 'no'}")
    lines.append(f"- New strategy stored: {'yes' if summary.get('strategy_persisted') else 'no'}")
    lines.append(f"- Failure recorded: {'yes' if summary.get('failure_recorded') else 'no'}")
    if summary.get("files_opened"):
        lines.append(f"- Files observed: {summary['files_opened']}")
    if summary.get("reopened_files"):
        lines.append(f"- Reopened files: {summary['reopened_files']}")
    tests = summary.get("tests_observed") if isinstance(summary.get("tests_observed"), list) else []
    if tests:
        lines.append("- Tests observed: " + ", ".join(f"`{item}`" for item in tests[:3]))
    return "\n".join(lines)


def build_agent_summary(
    prepared: dict[str, Any],
    learning: dict[str, Any] | None,
    strategy: dict[str, Any] | None,
    failure: dict[str, Any] | None,
) -> dict[str, Any]:
    execution_log = prepared.get("last_execution_log", {}) if isinstance(prepared.get("last_execution_log"), dict) else {}
    hint = prepared.get("execution_hint", {}) if isinstance(prepared.get("execution_hint"), dict) else {}
    summary = {
        "strategy_reused": bool(hint),
        "selection_reason": str(hint.get("selection_reason") or ""),
        "learning_persisted": bool(learning),
        "strategy_persisted": bool(strategy),
        "failure_recorded": bool(failure),
        "files_opened": len(execution_log.get("files_opened", [])) if isinstance(execution_log.get("files_opened"), list) else 0,
        "files_edited": len(execution_log.get("files_edited", [])) if isinstance(execution_log.get("files_edited"), list) else 0,
        "reopened_files": len(execution_log.get("files_reopened", [])) if isinstance(execution_log.get("files_reopened"), list) else 0,
        "commands_observed": list(execution_log.get("commands_executed", [])) if isinstance(execution_log.get("commands_executed"), list) else [],
        "tests_observed": list(execution_log.get("tests_executed", [])) if isinstance(execution_log.get("tests_executed"), list) else [],
    }
    return {"structured": summary, "rendered": render_agent_summary(summary)}


def finalize_execution(prepared: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    repo_root = Path(str(prepared.get("envelope", {}).get("repo_root") or ".")).resolve()
    normalized_result = {
        "success": bool(result.get("success")),
        "result_summary": str(result.get("result_summary", "") or ""),
        "validated_learning": bool(result.get("validated_learning")),
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
    agent_summary = build_agent_summary(prepared, learning, strategy, failure)
    persisted_feedback = persist_execution_feedback(repo_root, prepared, aictx_feedback, agent_summary["structured"])
    return {
        "execution_id": prepared["envelope"]["execution_id"],
        "execution_mode": prepared["execution_mode"],
        "telemetry_entry": telemetry_entry,
        "learning_persisted": learning,
        "strategy_persisted": strategy,
        "failure_persisted": failure,
        "resolved_failures": resolved_failures,
        "aictx_feedback": aictx_feedback,
        "feedback_persisted": persisted_feedback,
        "agent_summary": agent_summary["structured"],
        "agent_summary_text": agent_summary["rendered"],
        "value_evidence": {
            "task_fingerprint": prepared.get("task_fingerprint", ""),
            "repeated_context_request": bool(telemetry_entry.get("repeated_context_request")),
            "execution_time_ms": telemetry_entry.get("execution_time_ms"),
            "used_packet": False,
            "used_strategy": bool(telemetry_entry.get("used_strategy")),
            "files_opened": list(prepared.get("last_execution_log", {}).get("files_opened", [])) if isinstance(prepared.get("last_execution_log", {}).get("files_opened"), list) else [],
            "files_edited": list(prepared.get("last_execution_log", {}).get("files_edited", [])) if isinstance(prepared.get("last_execution_log", {}).get("files_edited"), list) else [],
            "files_reopened": list(prepared.get("last_execution_log", {}).get("files_reopened", [])) if isinstance(prepared.get("last_execution_log", {}).get("files_reopened"), list) else [],
            "commands_executed": list(prepared.get("last_execution_log", {}).get("commands_executed", [])) if isinstance(prepared.get("last_execution_log", {}).get("commands_executed"), list) else [],
            "tests_executed": list(prepared.get("last_execution_log", {}).get("tests_executed", [])) if isinstance(prepared.get("last_execution_log", {}).get("tests_executed"), list) else [],
        },
        "finalized_at": now_iso(),
    }


def cli_prepare_execution(args: argparse.Namespace) -> int:
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
        cli_value = list(getattr(args, field, []) or [])
        observation[field] = cli_value or list(observation.get(field, []) or [])
    prepared["execution_observation"] = observation
    result = {
        "success": bool(args.success),
        "result_summary": args.result_summary,
        "validated_learning": bool(args.validated_learning),
    }
    print(json.dumps(finalize_execution(prepared, result), indent=2, ensure_ascii=False))
    return 0

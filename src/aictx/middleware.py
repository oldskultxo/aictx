from __future__ import annotations

import argparse
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .adapters import resolve_adapter_profile
from . import core_runtime
from .runtime_contract import resolve_effective_preferences, runtime_consistency_report
from .runtime_io import slugify
from .runtime_memory import rank_records
from .runtime_tasks import packet_for_task, resolve_task_type
from .strategy_memory import build_strategy_entry, get_strategies_by_task_type, persist_strategy
from .state import (
    REPO_FAILURE_MEMORY_DIR,
    REPO_MEMORY_DIR,
    REPO_METRICS_DIR,
    REPO_TASK_MEMORY_DIR,
    read_json,
    write_json,
)

EXECUTION_LOG_PATH = REPO_METRICS_DIR / "agent_execution_log.jsonl"
REAL_EXECUTION_LOG_PATH = REPO_METRICS_DIR / "execution_logs.jsonl"
EXECUTION_FEEDBACK_PATH = REPO_METRICS_DIR / "execution_feedback.jsonl"
EXECUTION_STATUS_PATH = REPO_METRICS_DIR / "agent_execution_status.json"
FAILURE_EVENTS_DIR = REPO_FAILURE_MEMORY_DIR / "failures"
HEURISTIC_SKILL_PATTERN = re.compile(r"(\$[A-Za-z0-9:_-]+|SKILL\.md|\bskill\b)", re.IGNORECASE)


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
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
    lowered = str(user_request or "").lower()
    if execution_mode == "skill":
        return True
    if str(declared_task_type or "").strip().lower() not in {"", "unknown"}:
        return True
    if len(lowered.split()) >= 6:
        return True
    return any(keyword in lowered for keyword in ["fix", "debug", "implement", "refactor", "migrate", "test", "packet"])


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
        "files_reopened": [str(item) for item in payload.get("files_reopened", []) if str(item).strip()] if isinstance(payload.get("files_reopened"), list) else [],
    }


def load_bootstrap_sources(repo_root: Path) -> dict[str, Any]:
    memory_root = repo_root / REPO_MEMORY_DIR
    return {
        "derived_boot_summary": read_json(memory_root / "derived_boot_summary.json", {}),
        "user_preferences": read_json(memory_root / "user_preferences.json", {}),
        "project_bootstrap": read_json(memory_root / "project_bootstrap.json", {}),
    }


def prepare_execution(payload: dict[str, Any]) -> dict[str, Any]:
    envelope = build_execution_envelope(payload)
    repo_root = Path(envelope["repo_root"])
    boot_sources = load_bootstrap_sources(repo_root)
    adapter_profile = resolve_adapter_profile(envelope.get("adapter_id"), envelope.get("agent_id"), repo_root=repo_root)
    execution = classify_execution(envelope)
    resolved_preferences = resolve_effective_preferences(repo_root, global_defaults_path=core_runtime.ROOT_PREFS_PATH)
    communication_policy = dict(resolved_preferences.get("effective_preferences", {}).get("communication", {}))
    task_resolution = resolve_task_type(
        envelope["user_request"],
        explicit_task_type=envelope.get("declared_task_type"),
    )
    retrieval_matches = [
        row
        for row in rank_records(envelope["user_request"], project=repo_root.name)[:5]
        if row.get("type") != "user_preference"
    ]
    retrieval_summary = {
        "memory_records_considered": len(retrieval_matches),
        "memory_titles": [str(row.get("title") or row.get("id") or "") for row in retrieval_matches[:3]],
        "boot_pref_language": str(boot_sources.get("user_preferences", {}).get("preferred_language", "")),
    }
    task_fingerprint = slugify(f"{repo_root.name}:{task_resolution['task_type']}:{envelope['user_request']}")[:80]
    packet = None
    packet_path = ""
    if should_prepare_packet(
        envelope["user_request"],
        execution["execution_mode"],
        envelope.get("declared_task_type"),
    ):
        packet = packet_for_task(
            envelope["user_request"],
            project=repo_root.name,
            task_type=envelope.get("declared_task_type"),
        )
        packet_path = str(packet.get("packet_path") or "")
        if not packet_path:
            packet_path = str(core_runtime.read_json(core_runtime.COST_STATUS_PATH, {}).get("last_packet_path", "") or "")
        retrieval_summary.update(
            {
                "packet_built": True,
                "relevant_memory_count": len(packet.get("relevant_memory", [])),
                "knowledge_artifact_count": len(packet.get("knowledge_artifacts", [])),
                "failure_memory_reused": bool(packet.get("failure_memory", {}).get("failure_memory_used")),
                "task_memory_reused": bool(packet.get("task_memory", {}).get("task_specific_memory_used")),
                "repo_scope_count": len(packet.get("repo_scope", [])),
            }
        )
    else:
        retrieval_summary["packet_built"] = False
    strategies = get_strategies_by_task_type(repo_root, task_resolution["task_type"], include_failures=False)
    selected_strategy = strategies[-1] if strategies else None
    telemetry_targets = {
        "execution_log": (repo_root / EXECUTION_LOG_PATH).as_posix(),
        "execution_logs": (repo_root / REAL_EXECUTION_LOG_PATH).as_posix(),
        "execution_feedback": (repo_root / EXECUTION_FEEDBACK_PATH).as_posix(),
        "execution_status": (repo_root / EXECUTION_STATUS_PATH).as_posix(),
        "weekly_summary": (repo_root / REPO_METRICS_DIR / "weekly_summary.json").as_posix(),
        "workflow_learnings": (repo_root / REPO_MEMORY_DIR / "workflow_learnings.jsonl").as_posix(),
    }
    prepared = {
        "envelope": envelope,
        "execution_mode": execution["execution_mode"],
        "skill_metadata": execution["skill_metadata"],
        "skill_detection": execution["skill_detection"],
        "resolved_task_type": task_resolution["task_type"],
        "task_resolution": task_resolution,
        "task_fingerprint": task_fingerprint,
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
        "packet_path": packet_path,
        "packet": packet or {},
        "retrieval_summary": retrieval_summary,
        "telemetry_targets": telemetry_targets,
        "prepared_at": now_iso(),
        "execution_observation": {
            "task_id": str((packet or {}).get("task_id") or envelope["execution_id"]),
            "timestamp": now_iso(),
            "start_time_ms": int(time.time() * 1000),
            "task_type": task_resolution["task_type"],
            "files_opened": list(envelope.get("files_opened", [])),
            "files_reopened": list(envelope.get("files_reopened", [])),
            "execution_time_ms": None,
            "success": None,
            "used_packet": bool(retrieval_summary.get("packet_built")),
            "used_strategy": bool(selected_strategy),
        },
    }
    if selected_strategy:
        prepared["execution_hint"] = {
            "entry_points": list(selected_strategy.get("entry_points", [])) if isinstance(selected_strategy.get("entry_points"), list) else [],
            "files_used": list(selected_strategy.get("files_used", [])) if isinstance(selected_strategy.get("files_used"), list) else [],
            "based_on": "previous_successful_execution",
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
            "confidence": execution["skill_detection"].get("confidence", "low"),
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
    execution_time_ms = None
    if isinstance(started_ms, int):
        execution_time_ms = max(0, finished_ms - started_ms)
    entry = {
        "execution_id": prepared["envelope"]["execution_id"],
        "agent_id": prepared["envelope"]["agent_id"],
        "execution_mode": prepared["execution_mode"],
        "resolved_task_type": prepared["resolved_task_type"],
        "task_fingerprint": prepared.get("task_fingerprint", ""),
        "success": bool(result.get("success")),
        "validated_learning": bool(result.get("validated_learning")),
        "packet_path": prepared.get("packet_path", ""),
        "packet_built": bool(prepared.get("retrieval_summary", {}).get("packet_built")),
        "repeated_context_request": prior_total > 0,
        "task_memory_reused": bool(prepared.get("retrieval_summary", {}).get("task_memory_reused")),
        "failure_memory_reused": bool(prepared.get("retrieval_summary", {}).get("failure_memory_reused")),
        "repo_scope_count": int(prepared.get("retrieval_summary", {}).get("repo_scope_count", 0) or 0),
        "skill_detection": prepared.get("skill_detection", {}),
        "skill_metadata": prepared.get("skill_metadata", {}) if prepared.get("execution_mode") == "skill" else {},
        "result_summary": str(result.get("result_summary", "") or ""),
        "execution_time_ms": execution_time_ms,
        "used_strategy": bool(observation.get("used_strategy")),
        "recorded_at": now_iso(),
    }
    real_entry = {
        "task_id": str(observation.get("task_id") or prepared["envelope"]["execution_id"]),
        "timestamp": str(observation.get("timestamp") or prepared.get("prepared_at") or now_iso()),
        "task_type": prepared["resolved_task_type"],
        "files_opened": list(observation.get("files_opened", [])) if isinstance(observation.get("files_opened"), list) else [],
        "files_reopened": list(observation.get("files_reopened", [])) if isinstance(observation.get("files_reopened"), list) else [],
        "execution_time_ms": execution_time_ms,
        "success": bool(result.get("success")),
        "used_packet": bool(prepared.get("retrieval_summary", {}).get("packet_built")),
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
    weekly = read_json(weekly_path, {"version": 3, "tasks_sampled": 0, "repeated_tasks": 0, "phase_events_sampled": 0})
    weekly["tasks_sampled"] = int(weekly.get("tasks_sampled", 0) or 0) + 1
    weekly["repeated_tasks"] = int(weekly.get("repeated_tasks", 0) or 0) + (1 if prior_total else 0)
    weekly["last_execution_id"] = prepared["envelope"]["execution_id"]
    weekly["last_execution_mode"] = prepared["execution_mode"]
    weekly["last_execution_at"] = entry["recorded_at"]
    weekly["last_execution_success"] = bool(result.get("success"))
    weekly["last_execution_time_ms"] = execution_time_ms
    weekly["measurement_basis"] = "execution_logs"
    weekly["evidence_status"] = "unknown"
    weekly["metrics"] = {
        "observed": {
            "tasks_sampled": int(weekly.get("tasks_sampled", 0) or 0),
            "repeated_tasks": int(weekly.get("repeated_tasks", 0) or 0),
            "phase_events_sampled": int(weekly.get("phase_events_sampled", 0) or 0),
            "last_execution_time_ms": execution_time_ms,
        }
    }
    weekly["value_evidence"] = {
        "repeated_tasks_observed": int(weekly.get("repeated_tasks", 0) or 0),
        "tasks_using_task_memory": int((weekly.get("value_evidence", {}) or {}).get("tasks_using_task_memory", 0) or 0) + (1 if entry["task_memory_reused"] else 0),
        "tasks_using_failure_memory": int((weekly.get("value_evidence", {}) or {}).get("tasks_using_failure_memory", 0) or 0) + (1 if entry["failure_memory_reused"] else 0),
        "last_task_fingerprint": prepared.get("task_fingerprint", ""),
        "last_execution_time_ms": execution_time_ms,
        "last_used_packet": real_entry["used_packet"],
        "files_opened": real_entry["files_opened"],
        "files_reopened": real_entry["files_reopened"],
    }
    if prepared["execution_mode"] == "skill":
        weekly["last_skill_name"] = prepared.get("skill_metadata", {}).get("skill_name", "")
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
    task_status_path = repo_root / REPO_TASK_MEMORY_DIR / "task_memory_status.json"
    task_status = read_json(task_status_path, {"version": 1, "records_by_task_type": {}})
    records_by_task_type = dict(task_status.get("records_by_task_type", {}))
    task_type = prepared["resolved_task_type"]
    records_by_task_type[task_type] = int(records_by_task_type.get(task_type, 0) or 0) + 1
    task_status["records_by_task_type"] = records_by_task_type
    task_status["last_execution_id"] = prepared["envelope"]["execution_id"]
    task_status["last_task_type"] = task_type
    write_json(task_status_path, task_status)
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
    used_strategy = bool(prepared.get("execution_hint")) or bool(telemetry_entry.get("used_strategy"))
    files_opened_count = len(files_opened)
    files_reopened_count = len(files_reopened)
    return {
        "files_opened": files_opened_count,
        "reopened_files": files_reopened_count,
        "used_strategy": used_strategy,
        "used_packet": bool(telemetry_entry.get("packet_built")),
        "possible_redundant_exploration": bool(files_reopened_count > 0 or files_opened_count > 5),
        "previous_strategy_reused": used_strategy,
    }



def persist_execution_feedback(repo_root: Path, prepared: dict[str, Any], feedback: dict[str, Any]) -> dict[str, Any]:
    path = repo_root / EXECUTION_FEEDBACK_PATH
    payload = {
        "task_id": str(prepared.get("execution_observation", {}).get("task_id") or prepared.get("envelope", {}).get("execution_id") or ""),
        "execution_id": str(prepared.get("envelope", {}).get("execution_id") or ""),
        "timestamp": now_iso(),
        "aictx_feedback": feedback,
    }
    append_jsonl(path, payload)
    return payload


def persist_failure_event(repo_root: Path, prepared: dict[str, Any], result: dict[str, Any]) -> dict[str, Any] | None:
    if result.get("success"):
        return None
    summary = str(result.get("result_summary") or "").strip() or "execution_failed"
    failure_id = f"{prepared['envelope']['execution_id']}_{core_runtime.slugify(summary)[:32]}"
    failure_payload = {
        "failure_id": failure_id,
        "execution_id": prepared["envelope"]["execution_id"],
        "task_type": prepared["resolved_task_type"],
        "execution_mode": prepared["execution_mode"],
        "summary": summary,
        "skill_detection": prepared.get("skill_detection", {}),
        "recorded_at": now_iso(),
    }
    path = repo_root / FAILURE_EVENTS_DIR / f"{failure_id}.json"
    write_json(path, failure_payload)
    status_path = repo_root / REPO_FAILURE_MEMORY_DIR / "failure_memory_status.json"
    status = read_json(status_path, {"version": 1, "records_total": 0})
    status["records_total"] = int(status.get("records_total", 0) or 0) + 1
    status["last_failure_id"] = failure_id
    status["last_execution_id"] = prepared["envelope"]["execution_id"]
    write_json(status_path, status)
    return {"path": path.as_posix(), "failure_id": failure_id}


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
    failure = persist_failure_event(repo_root, prepared, normalized_result)
    aictx_feedback = build_aictx_feedback(prepared, telemetry_entry)
    persisted_feedback = persist_execution_feedback(repo_root, prepared, aictx_feedback)
    return {
        "execution_id": prepared["envelope"]["execution_id"],
        "execution_mode": prepared["execution_mode"],
        "telemetry_entry": telemetry_entry,
        "learning_persisted": learning,
        "strategy_persisted": strategy,
        "failure_recorded": failure,
        "aictx_feedback": aictx_feedback,
        "feedback_persisted": persisted_feedback,
        "value_evidence": {
            "task_fingerprint": prepared.get("task_fingerprint", ""),
            "task_memory_reused": bool(telemetry_entry.get("task_memory_reused")),
            "failure_memory_reused": bool(telemetry_entry.get("failure_memory_reused")),
            "repeated_context_request": bool(telemetry_entry.get("repeated_context_request")),
            "execution_time_ms": telemetry_entry.get("execution_time_ms"),
            "used_packet": bool(telemetry_entry.get("packet_built")),
            "used_strategy": bool(telemetry_entry.get("used_strategy")),
            "files_opened": [],
            "files_reopened": [],
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
        "files_reopened": list(args.files_reopened or []),
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
    observation["files_opened"] = list(args.files_opened or observation.get("files_opened", []) or [])
    observation["files_reopened"] = list(args.files_reopened or observation.get("files_reopened", []) or [])
    prepared["execution_observation"] = observation
    result = {
        "success": bool(args.success),
        "result_summary": args.result_summary,
        "validated_learning": bool(args.validated_learning),
    }
    print(json.dumps(finalize_execution(prepared, result), indent=2, ensure_ascii=False))
    return 0

from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any

from .runtime_io import days_since, slugify


def route_task(task: str) -> dict[str, Any]:
    return {
        "task": task,
        "mode": "deterministic",
    }


def resolve_task_type(
    task: str,
    *,
    explicit_task_type: str | None = None,
    packet_metadata: dict[str, Any] | None = None,
    touched_files: list[str] | None = None,
) -> dict[str, Any]:
    from . import core_runtime as cr

    task_signals = cr.infer_task_signals(task, touched_files=touched_files)
    normalized_explicit = cr.normalize_task_type(explicit_task_type)
    if explicit_task_type and normalized_explicit in cr.TASK_TYPES:
        return {
            "task_type": normalized_explicit,
            "source": "explicit_task_type",
            "fallback": normalized_explicit == "unknown",
            "confidence": 0.95,
            "signals": [f"explicit:{normalized_explicit}"],
            "evidence": [f"user_declared:{normalized_explicit}"],
            "ambiguous": normalized_explicit == "unknown",
        }
    metadata_task_type = cr.normalize_task_type((packet_metadata or {}).get("task_type"))
    if packet_metadata and packet_metadata.get("task_type") and metadata_task_type in cr.TASK_TYPES:
        return {
            "task_type": metadata_task_type,
            "source": "packet_metadata",
            "fallback": metadata_task_type == "unknown",
            "confidence": 0.9,
            "signals": [f"metadata:{metadata_task_type}"],
            "evidence": [f"packet_metadata:{metadata_task_type}"],
            "ambiguous": metadata_task_type == "unknown",
        }
    inferred = cr.classify_task_type_from_text("\n".join([task, " ".join(touched_files or [])]), tags=[], record_type=None)
    evidence = task_signals[:6]
    ambiguity_markers = len({signal.split(":")[1] for signal in task_signals if ":" in signal}) >= 2
    if inferred != "unknown":
        confidence = cr.task_type_confidence(task, inferred, touched_files=touched_files)
        return {
            "task_type": inferred,
            "source": "heuristic_inference",
            "fallback": False,
            "confidence": confidence,
            "signals": task_signals,
            "evidence": evidence or [f"heuristic:{inferred}"],
            "ambiguous": confidence < 0.68 or ambiguity_markers,
        }
    return {
        "task_type": "unknown",
        "source": "unknown_fallback",
        "fallback": True,
        "confidence": 0.35,
        "signals": task_signals,
        "evidence": evidence or ["no_strong_task_type_signal"],
        "ambiguous": True,
    }


def packet_for_task(
    task: str | dict[str, Any],
    ctx: dict[str, Any] | None = None,
    *,
    project: str | None = None,
    task_type: str | None = None,
) -> dict[str, Any]:
    if isinstance(task, dict):
        task_payload = dict(task)
        task_description = str(task_payload.get("description", "") or "")
        resolved_task_type = str(task_payload.get("task_type", "unknown") or "unknown")
        context = dict((ctx or {}).get("context", {})) if isinstance(ctx, dict) else {}
        return {
            "task_type": resolved_task_type,
            "description": task_description,
            "context": context,
        }

    resolved = resolve_task_type(task, explicit_task_type=task_type)
    return {
        "task_id": f"{date.today().isoformat()}_{slugify(task)[:40]}",
        "task": task,
        "task_summary": task,
        "task_type": resolved["task_type"],
        "task_type_resolution": resolved,
        "project": project,
        "repo_scope": [],
        "relevant_paths": [],
        "architecture_rules": [],
        "architecture_decisions": [],
        "context": {},
        "description": task,
    }


def detect_stale_records() -> dict[str, Any]:
    from . import core_runtime as cr
    from .runtime_memory import load_records, normalize_record

    rows = [normalize_record(row) for row in load_records()]
    stale = []
    duplicate_groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    missing_paths = []
    today = date.today().isoformat()
    for row in rows:
        verified = str(row.get("last_verified", ""))
        if verified and verified < "2026-01-01":
            stale.append({"id": row["id"], "last_verified": verified})
        duplicate_groups[(str(row.get("type")), str(row.get("title", row.get("key", ""))))].append(row["id"])
        rel_path = row.get("path")
        if rel_path and not (cr.BASE / rel_path).exists():
            missing_paths.append({"id": row["id"], "path": rel_path})
    duplicates = [{"type": group[0], "title": group[1], "record_ids": ids} for group, ids in duplicate_groups.items() if len(ids) > 1]
    report = {"generated_at": today, "stale": stale, "duplicates": duplicates, "missing_paths": missing_paths}
    cr.write_json(cr.BASE / "staleness_report.json", report)
    return report


def compact_records(apply: bool = False) -> dict[str, Any]:
    from . import core_runtime as cr
    from .runtime_memory import load_records, normalize_record

    rows = [normalize_record(row) for row in load_records()]
    stale = []
    duplicates = []
    verbose = []
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("type") == "user_preference":
            signature = f"pref:{row.get('key', row.get('id', ''))}"
        elif row.get("path"):
            signature = f"path:{row.get('path')}"
        elif row.get("title") or row.get("summary"):
            signature_text = f"{row.get('title', '')} {row.get('summary', '')}"
            signature = f"text:{slugify(signature_text)}"
        else:
            signature = f"id:{row.get('id', '')}"
        key = (str(row.get("type", "")), signature)
        grouped[key].append(row)
        if len(str(row.get("summary", ""))) > 320:
            verbose.append(row["id"])
        if days_since(row.get("last_used_at")) > 180 and float(row.get("relevance_score", 0.6)) < 0.5:
            stale.append(row["id"])
    for key, group in grouped.items():
        if len(group) > 1:
            duplicates.append({"type": key[0], "signature": key[1], "record_ids": [row["id"] for row in group], "kept_id": sorted(group, key=lambda row: (-float(row.get("success_rate", 0.75)), row["context_cost"], row["id"]))[0]["id"]})
    report = {
        "generated_at": date.today().isoformat(), "dry_run": not apply, 'stores_scanned': len(list(cr.PROJECT_RECORDS_DIR.glob('*.jsonl'))) + 2,
        'duplicates_detected': len(duplicates), 'near_duplicates_detected': 0, 'stale_records_detected': len(stale), 'verbose_records_detected': len(verbose), 'fragmented_groups_detected': 0,
        'actions': [
            *[{'type': 'duplicate', 'record_ids': item['record_ids'], 'kept_id': item['kept_id'], 'recommendation': 'merge_or_prune'} for item in duplicates],
            *[{'type': 'stale_low_value', 'record_id': record_id, 'recommendation': 'review'} for record_id in stale],
            *[{'type': 'verbose', 'record_id': record_id, 'recommendation': 'tighten_summary'} for record_id in verbose],
        ],
    }
    cr.write_json(cr.ROOT_COMPACTION_REPORT_PATH, report)
    return report

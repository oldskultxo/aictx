#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .runtime_contract import runtime_consistency_report
from .runtime_versioning import normalize_engine_capability_version, normalize_installed_version

BASE = Path(__file__).resolve().parents[2]
PROJECTS_ROOT = BASE.parent
CANONICAL_SCOPE = BASE.name
GLOBAL_DIR = BASE / ".ai_context_global_metrics"
PROJECTS_INDEX_PATH = GLOBAL_DIR / "projects_index.json"
CONTEXT_SAVINGS_PATH = GLOBAL_DIR / "global_context_savings.json"
TOKEN_SAVINGS_PATH = GLOBAL_DIR / "global_token_savings.json"
LATENCY_METRICS_PATH = GLOBAL_DIR / "global_latency_metrics.json"
HEALTH_REPORT_PATH = GLOBAL_DIR / "system_health_report.json"
TELEMETRY_SOURCES_PATH = GLOBAL_DIR / "telemetry_sources.json"
MIN_CAPABILITY_COST_OPTIMIZER = 5
MIN_CAPABILITY_TASK_MEMORY = 6
MIN_CAPABILITY_FAILURE_MEMORY = 7
MIN_CAPABILITY_MEMORY_GRAPH = 9


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return {} if default is None else default
    return json.loads(path.read_text())


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def rel(path: Path) -> str:
    return path.as_posix()


@dataclass
class ProjectTelemetry:
    context_range: tuple[float, float] | None = None
    context_point: float | None = None
    token_range: tuple[float, float] | None = None
    latency_range: tuple[float, float] | None = None
    cost_range: tuple[float, float] | None = None
    confidence: str = "unknown"
    tasks_sampled: int = 0
    repeated_tasks: int = 0
    source: str = "unknown"
    generated_at: str | None = None
    optimization_events: int = 0
    optimizer_status: str = "unknown"
    task_memory_records: int = 0
    task_memory_enabled: bool = False
    failure_memory_records: int = 0
    failure_memory_enabled: bool = False
    memory_graph_nodes: int = 0
    memory_graph_edges: int = 0
    memory_graph_enabled: bool = False
    phase_events_sampled: int = 0
    telemetry_granularity: str = "task_only"
    knowledge_mods_enabled: bool = False
    knowledge_retrieval_enabled: bool = False
    evidence_status: str = "unknown"
    measurement_basis: str = "unknown"


@dataclass
class ProjectEntry:
    name: str
    repo_path: Path
    telemetry_dir: Path | None
    memory_dir: Path | None
    installed_version: str
    engine_capability_version: int | None
    installed_iteration: str
    source: str


ENGINE_DIRNAME = ".ai_context_engine"
ENGINE_MEMORY_DIR = Path(ENGINE_DIRNAME) / "memory"
ENGINE_COST_DIR = Path(ENGINE_DIRNAME) / "cost"
ENGINE_TASK_MEMORY_DIR = Path(ENGINE_DIRNAME) / "task_memory"
ENGINE_FAILURE_MEMORY_DIR = Path(ENGINE_DIRNAME) / "failure_memory"
ENGINE_MEMORY_GRAPH_DIR = Path(ENGINE_DIRNAME) / "memory_graph"
ENGINE_LIBRARY_DIR = Path(ENGINE_DIRNAME) / "library"
ENGINE_METRICS_DIR = Path(ENGINE_DIRNAME) / "metrics"


def repo_engine_dir(repo: Path) -> Path:
    return repo / ENGINE_DIRNAME


def repo_memory_dir(repo: Path) -> Path:
    return repo / ENGINE_MEMORY_DIR


def repo_cost_dir(repo: Path) -> Path:
    return repo / ENGINE_COST_DIR


def repo_task_memory_dir(repo: Path) -> Path:
    return repo / ENGINE_TASK_MEMORY_DIR


def repo_failure_memory_dir(repo: Path) -> Path:
    return repo / ENGINE_FAILURE_MEMORY_DIR


def repo_memory_graph_dir(repo: Path) -> Path:
    return repo / ENGINE_MEMORY_GRAPH_DIR


def repo_library_dir(repo: Path) -> Path:
    return repo / ENGINE_LIBRARY_DIR


def repo_metrics_dir(repo: Path) -> Path:
    return repo / ENGINE_METRICS_DIR


def detect_repo_dirs(root: Path) -> list[Path]:
    repos: list[Path] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        if child.name == "__pycache__":
            continue
        markers = [
            child / "AGENTS.md",
            child / ".git",
            child / ENGINE_DIRNAME,
        ]
        if any(marker.exists() for marker in markers):
            repos.append(child)
    return repos


def capability_at_least(value: int | None, minimum: int) -> bool:
    return value is not None and value >= minimum


def infer_installed_version(repo: Path) -> str:
    engine_state = read_json(repo_engine_dir(repo) / "state.json", {})
    explicit_version = normalize_installed_version(engine_state.get("installed_version"), fallback="unknown")
    return explicit_version


def infer_engine_capability_version(repo: Path) -> int | None:
    engine_state = read_json(repo_engine_dir(repo) / "state.json", {})
    explicit_capability = normalize_engine_capability_version(
        engine_state.get("engine_capability_version"),
        legacy_iteration=engine_state.get("installed_iteration"),
    )
    if explicit_capability is not None:
        return explicit_capability
    if repo.name == CANONICAL_SCOPE:
        if (repo_library_dir(repo) / "retrieval_status.json").exists():
            retrieval_status = read_json(repo_library_dir(repo) / "retrieval_status.json", {})
            retrieval_capability = normalize_engine_capability_version(
                retrieval_status.get("engine_capability_version"),
                legacy_iteration=retrieval_status.get("installed_iteration"),
            )
            if retrieval_capability is not None:
                return retrieval_capability
            if retrieval_status.get("supports_remote_ingestion"):
                return 15
            if retrieval_status.get("supports_reference_ingestion"):
                return 14
            return 13
        if (repo_library_dir(repo) / "registry.json").exists():
            return 12 if any((repo_library_dir(repo) / "mods").glob("*/indices/*.json")) else 11
        if (repo_metrics_dir(repo) / "weekly_summary.json").exists():
            weekly = read_json(repo_metrics_dir(repo) / "weekly_summary.json", {})
            if weekly.get("phase_events_sampled") is not None or weekly.get("telemetry_granularity") == "task_plus_phase":
                return 10
        if (repo_memory_graph_dir(repo) / "graph_status.json").exists():
            return 9
        if (repo_task_memory_dir(repo) / "task_taxonomy.json").exists():
            return 8
        if (repo_failure_memory_dir(repo) / "failure_memory_status.json").exists():
            return 7
        if (repo_task_memory_dir(repo) / "task_memory_status.json").exists():
            return 6
        return 5 if (repo_cost_dir(repo) / "packet_budget_status.json").exists() else 4
    has_memory = repo_memory_dir(repo).exists()
    has_metrics = repo_metrics_dir(repo).exists()
    has_cost = (repo_cost_dir(repo) / "packet_budget_status.json").exists()
    has_task_memory = (repo_task_memory_dir(repo) / "task_memory_status.json").exists()
    has_failure_memory = (repo_failure_memory_dir(repo) / "failure_memory_status.json").exists()
    has_memory_graph = (repo_memory_graph_dir(repo) / "graph_status.json").exists()
    task_memory_summary = read_json(repo_task_memory_dir(repo) / "task_memory_status.json", {}) if has_task_memory else {}
    agents_text = (repo / "AGENTS.md").read_text(encoding="utf-8", errors="ignore") if (repo / "AGENTS.md").exists() else ""
    if has_memory_graph:
        return 9
    if has_task_memory and int(task_memory_summary.get("task_taxonomy_version", 0) or 0) >= 2:
        return 8
    if has_failure_memory:
        return 7
    if has_task_memory:
        return 6
    if has_cost:
        return 5
    if "global reporting" in agents_text.lower() or "health check" in agents_text.lower() or repo.name == "iepub":
        return 4
    if has_memory and has_metrics:
        return 3
    if has_memory:
        return 2
    if "ai_context_engine" in agents_text:
        return 1
    return None


def discover_projects() -> list[ProjectEntry]:
    entries: list[ProjectEntry] = []
    for repo in detect_repo_dirs(PROJECTS_ROOT):
        has_memory = repo_memory_dir(repo)
        has_metrics = repo_metrics_dir(repo)
        agents = repo / "AGENTS.md"
        if not (has_memory.exists() or has_metrics.exists() or agents.exists()):
            continue
        capability_version = infer_engine_capability_version(repo)
        entries.append(
            ProjectEntry(
                name=repo.name,
                repo_path=repo,
                telemetry_dir=has_metrics if has_metrics.exists() else None,
                memory_dir=has_memory if has_memory.exists() else None,
                installed_version=infer_installed_version(repo),
                engine_capability_version=capability_version,
                installed_iteration=str(capability_version or "unknown"),
                source="auto_discovered",
            )
        )
    return entries


def load_context_savings_markdown(repo: Path) -> dict[str, Any]:
    path = repo / "CONTEXT_SAVINGS.md"
    if not path.exists():
        return {"exists": False, "checkpoints": 0}
    text = path.read_text(encoding="utf-8", errors="ignore")
    checkpoints = sum(1 for line in text.splitlines() if line.strip().startswith("## ") or line.strip().startswith("### "))
    return {
        "exists": True,
        "path": rel(path),
        "checkpoints": checkpoints,
        "bytes": path.stat().st_size,
    }


def load_project_telemetry(repo: Path) -> ProjectTelemetry:
    weekly = repo_metrics_dir(repo) / "weekly_summary.json"
    cost_status_path = repo_cost_dir(repo) / "packet_budget_status.json"
    task_status_path = repo_task_memory_dir(repo) / "task_memory_status.json"
    failure_status_path = repo_failure_memory_dir(repo) / "failure_memory_status.json"
    memory_graph_status_path = repo_memory_graph_dir(repo) / "graph_status.json"
    library_registry_path = repo_library_dir(repo) / "registry.json"
    retrieval_status_path = repo_library_dir(repo) / "retrieval_status.json"
    cost_status = read_json(cost_status_path, {}) if cost_status_path.exists() else {}
    task_status = read_json(task_status_path, {}) if task_status_path.exists() else {}
    failure_status = read_json(failure_status_path, {}) if failure_status_path.exists() else {}
    memory_graph_status = read_json(memory_graph_status_path, {}) if memory_graph_status_path.exists() else {}
    library_registry = read_json(library_registry_path, {}) if library_registry_path.exists() else {}
    retrieval_status = read_json(retrieval_status_path, {}) if retrieval_status_path.exists() else {}
    if weekly.exists():
        payload = read_json(weekly, {})
        context_range = None
        token_range = None
        latency_range = None
        cost_range = None
        tasks_sampled = int(payload.get("tasks_sampled", 0) or 0)
        evidence_status = str(payload.get("evidence_status", "unknown"))
        measurement_basis = str(payload.get("measurement_basis", "execution_logs"))
        return ProjectTelemetry(
            context_range=context_range,
            context_point=context.get("point"),
            token_range=token_range,
            latency_range=latency_range,
            cost_range=cost_range,
            confidence=str(payload.get("confidence", "unknown")),
            tasks_sampled=tasks_sampled,
            repeated_tasks=int(payload.get("repeated_tasks", 0) or 0),
            source=rel(weekly),
            generated_at=str(payload.get("generated_at") or ""),
            optimization_events=int(cost_status.get("optimization_events", 0) or 0),
            optimizer_status=str(cost_status.get("last_status", "unknown")),
            task_memory_records=sum(int(v or 0) for v in task_status.get("records_by_task_type", {}).values()),
            task_memory_enabled=bool(task_status),
            failure_memory_records=int(failure_status.get("records_total", 0) or 0),
            failure_memory_enabled=bool(failure_status),
            memory_graph_nodes=int(memory_graph_status.get("nodes_total", 0) or 0),
            memory_graph_edges=int(memory_graph_status.get("edges_total", 0) or 0),
            memory_graph_enabled=bool(memory_graph_status),
            phase_events_sampled=int(payload.get("phase_events_sampled", 0) or 0),
            telemetry_granularity=str(payload.get("telemetry_granularity", "task_only")),
            knowledge_mods_enabled=bool(library_registry.get("mods")),
            knowledge_retrieval_enabled=bool(retrieval_status),
            evidence_status=evidence_status,
            measurement_basis=measurement_basis,
        )
    return ProjectTelemetry(
        optimization_events=int(cost_status.get("optimization_events", 0) or 0),
        optimizer_status=str(cost_status.get("last_status", "unknown")),
        task_memory_records=sum(int(v or 0) for v in task_status.get("records_by_task_type", {}).values()),
        task_memory_enabled=bool(task_status),
        failure_memory_records=int(failure_status.get("records_total", 0) or 0),
        failure_memory_enabled=bool(failure_status),
        memory_graph_nodes=int(memory_graph_status.get("nodes_total", 0) or 0),
        memory_graph_edges=int(memory_graph_status.get("edges_total", 0) or 0),
        memory_graph_enabled=bool(memory_graph_status),
        knowledge_mods_enabled=bool(library_registry.get("mods")),
        knowledge_retrieval_enabled=bool(retrieval_status),
        evidence_status="unknown",
        measurement_basis="unknown",
    )


def weighted_mean(values: list[tuple[float, int]]) -> float | None:
    total_weight = sum(weight for _, weight in values)
    if total_weight <= 0:
        return None
    return sum(value * weight for value, weight in values) / total_weight


def aggregate_range(projects: list[dict[str, Any]], field: str) -> dict[str, Any]:
    weighted_low: list[tuple[float, int]] = []
    weighted_high: list[tuple[float, int]] = []
    weighted_point: list[tuple[float, int]] = []
    contributing = 0
    excluded_insufficient_data = 0
    for project in projects:
        telemetry = project.get("telemetry", {})
        if str(telemetry.get("evidence_status", "unknown")) == "insufficient_data":
            excluded_insufficient_data += 1
            continue
        sample_weight = max(int(telemetry.get("tasks_sampled", 0) or 0), 1)
        range_value = telemetry.get(field)
        if isinstance(range_value, list) and len(range_value) == 2:
            weighted_low.append((float(range_value[0]), sample_weight))
            weighted_high.append((float(range_value[1]), sample_weight))
            contributing += 1
        if field == "context_range" and telemetry.get("context_point") is not None:
            weighted_point.append((float(telemetry["context_point"]), sample_weight))
    low = weighted_mean(weighted_low)
    high = weighted_mean(weighted_high)
    point = weighted_mean(weighted_point) if weighted_point else None
    return {
        "projects_with_telemetry": contributing,
        "projects_excluded_insufficient_data": excluded_insufficient_data,
        "range": [round(low, 4), round(high, 4)] if low is not None and high is not None else None,
        "point": round(point, 4) if point is not None else None,
    }


def contributors_by_status(projects: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"measured": 0, "estimated": 0, "insufficient_data": 0, "unknown": 0}
    for project in projects:
        status = str(project.get("telemetry", {}).get("evidence_status", "unknown"))
        if status not in counts:
            status = "unknown"
        counts[status] += 1
    return counts


def confidence_for_projects(projects: list[dict[str, Any]]) -> str:
    sample_total = sum(int(project.get("telemetry", {}).get("tasks_sampled", 0) or 0) for project in projects)
    contributors = sum(1 for project in projects if project.get("telemetry", {}).get("source") != "unknown")
    if sample_total >= 50 and contributors >= 3:
        return "high"
    if sample_total >= 10 and contributors >= 2:
        return "medium"
    if contributors >= 1:
        return "low"
    return "unknown"


def project_feature_flags(repo: Path, telemetry: ProjectTelemetry, row: dict[str, Any]) -> dict[str, bool]:
    capability_version = normalize_engine_capability_version(
        row.get("engine_capability_version"),
        legacy_iteration=row.get("installed_iteration"),
    )
    return {
        "packet_budget_status_found": (repo_cost_dir(repo) / "packet_budget_status.json").exists()
        or telemetry.optimization_events > 0
        or capability_at_least(capability_version, MIN_CAPABILITY_COST_OPTIMIZER),
        "task_memory_found": (repo_task_memory_dir(repo) / "task_memory_status.json").exists()
        or bool(telemetry.task_memory_enabled)
        or capability_at_least(capability_version, MIN_CAPABILITY_TASK_MEMORY),
        "failure_memory_found": (repo_failure_memory_dir(repo) / "failure_memory_status.json").exists()
        or bool(telemetry.failure_memory_enabled)
        or capability_at_least(capability_version, MIN_CAPABILITY_FAILURE_MEMORY),
        "memory_graph_found": (repo_memory_graph_dir(repo) / "graph_status.json").exists()
        or bool(telemetry.memory_graph_enabled)
        or capability_at_least(capability_version, MIN_CAPABILITY_MEMORY_GRAPH),
    }


def register_projects() -> dict[str, Any]:
    discovered = discover_projects()
    rows = []
    for entry in discovered:
        rows.append(
            {
                "name": entry.name,
                "repo_path": rel(entry.repo_path),
                "telemetry_dir": rel(entry.telemetry_dir) if entry.telemetry_dir else "unknown",
                "memory_dir": rel(entry.memory_dir) if entry.memory_dir else "unknown",
                "installed_version": entry.installed_version,
                "engine_capability_version": entry.engine_capability_version,
                "installed_iteration": entry.installed_iteration,
                "source": entry.source,
                "registered_at": now_iso(),
            }
        )
    payload = {
        "version": 1,
        "generated_at": now_iso(),
        "projects": rows,
    }
    write_json(PROJECTS_INDEX_PATH, payload)
    return payload


def refresh_global_metrics() -> dict[str, Any]:
    projects_index = register_projects()
    project_rows = []
    telemetry_sources = []
    for row in projects_index.get("projects", []):
        repo = Path(row["repo_path"])
        telemetry = load_project_telemetry(repo)
        savings_md = load_context_savings_markdown(repo)
        feature_flags = project_feature_flags(repo, telemetry, row)
        project_payload = {
            **row,
            "telemetry": {
                "context_range": list(telemetry.context_range) if telemetry.context_range else None,
                "context_point": telemetry.context_point,
                "token_range": list(telemetry.token_range) if telemetry.token_range else None,
                "latency_range": list(telemetry.latency_range) if telemetry.latency_range else None,
                "cost_range": list(telemetry.cost_range) if telemetry.cost_range else None,
                "confidence": telemetry.confidence,
                "tasks_sampled": telemetry.tasks_sampled,
                "repeated_tasks": telemetry.repeated_tasks,
                "source": telemetry.source,
                "generated_at": telemetry.generated_at,
                "optimization_events": telemetry.optimization_events,
                "optimizer_status": telemetry.optimizer_status,
                "task_memory_records": telemetry.task_memory_records,
                "task_memory_enabled": telemetry.task_memory_enabled,
                "failure_memory_records": telemetry.failure_memory_records,
                "failure_memory_enabled": telemetry.failure_memory_enabled,
                "memory_graph_nodes": telemetry.memory_graph_nodes,
                "memory_graph_edges": telemetry.memory_graph_edges,
                "memory_graph_enabled": telemetry.memory_graph_enabled,
                "evidence_status": telemetry.evidence_status,
                "measurement_basis": telemetry.measurement_basis,
            },
            "context_savings_markdown": savings_md,
        }
        project_rows.append(project_payload)
        telemetry_sources.append(
            {
                "project": row["name"],
                "repo_path": row["repo_path"],
                "telemetry_dir": row["telemetry_dir"],
                "weekly_summary_found": telemetry.source != "unknown",
                "weekly_summary_source": telemetry.source,
                "evidence_status": telemetry.evidence_status,
                "measurement_basis": telemetry.measurement_basis,
                **feature_flags,
                "context_savings_markdown": savings_md,
                "memory_dir": row["memory_dir"],
            }
        )

    capability_versions = Counter(str(project.get("engine_capability_version") or "unknown") for project in project_rows)
    projects_with_memory = sum(1 for project in project_rows if project["memory_dir"] != "unknown")
    projects_with_telemetry = sum(1 for project in project_rows if project["telemetry"]["source"] != "unknown")
    projects_with_cost_optimizer = sum(
        1 for project in project_rows if project_feature_flags(Path(project["repo_path"]), ProjectTelemetry(**project["telemetry"]), project)["packet_budget_status_found"]
    )
    projects_with_task_memory = sum(
        1 for project in project_rows if project_feature_flags(Path(project["repo_path"]), ProjectTelemetry(**project["telemetry"]), project)["task_memory_found"]
    )
    projects_with_failure_memory = sum(
        1 for project in project_rows if project_feature_flags(Path(project["repo_path"]), ProjectTelemetry(**project["telemetry"]), project)["failure_memory_found"]
    )
    projects_with_memory_graph = sum(
        1 for project in project_rows if project_feature_flags(Path(project["repo_path"]), ProjectTelemetry(**project["telemetry"]), project)["memory_graph_found"]
    )
    context = aggregate_range(project_rows, "context_range")
    token = aggregate_range(project_rows, "token_range")
    latency = aggregate_range(project_rows, "latency_range")
    confidence = confidence_for_projects(project_rows)
    status_breakdown = contributors_by_status(project_rows)
    claim_label = "material_repeatable" if status_breakdown.get("measured", 0) >= 3 else "exploratory"

    context_payload = {
        "version": 1,
        "generated_at": now_iso(),
        "projects_detected": len(project_rows),
        "projects_with_memory": projects_with_memory,
        "projects_with_telemetry": projects_with_telemetry,
        "projects_with_cost_optimizer": projects_with_cost_optimizer,
        "projects_with_task_memory": projects_with_task_memory,
        "projects_with_failure_memory": projects_with_failure_memory,
        "projects_with_memory_graph": projects_with_memory_graph,
        "projects_by_capability_version": dict(sorted(capability_versions.items())),
        "projects_by_iteration": dict(sorted(Counter(project["installed_iteration"] for project in project_rows).items())),
        "estimated_context_reduction": context,
        "confidence": confidence,
        "contributors_by_status": status_breakdown,
        "claim_label": claim_label,
        "unknown_projects": [project["name"] for project in project_rows if project["telemetry"]["source"] == "unknown"],
        "project_breakdown": project_rows,
    }
    token_payload = {
        "version": 1,
        "generated_at": now_iso(),
        "projects_detected": len(project_rows),
        "projects_with_telemetry": projects_with_telemetry,
        "projects_with_cost_optimizer": projects_with_cost_optimizer,
        "projects_with_task_memory": projects_with_task_memory,
        "projects_with_failure_memory": projects_with_failure_memory,
        "projects_with_memory_graph": projects_with_memory_graph,
        "projects_by_capability_version": dict(sorted(capability_versions.items())),
        "projects_by_iteration": context_payload["projects_by_iteration"],
        "estimated_total_token_reduction": token,
        "confidence": confidence,
        "contributors_by_status": status_breakdown,
        "claim_label": claim_label,
        "unknown_projects": context_payload["unknown_projects"],
    }
    latency_payload = {
        "version": 1,
        "generated_at": now_iso(),
        "projects_detected": len(project_rows),
        "projects_with_telemetry": projects_with_telemetry,
        "projects_with_cost_optimizer": projects_with_cost_optimizer,
        "projects_with_task_memory": projects_with_task_memory,
        "projects_with_failure_memory": projects_with_failure_memory,
        "projects_with_memory_graph": projects_with_memory_graph,
        "projects_by_capability_version": dict(sorted(capability_versions.items())),
        "projects_by_iteration": context_payload["projects_by_iteration"],
        "estimated_latency_improvement": latency,
        "confidence": confidence,
        "contributors_by_status": status_breakdown,
        "claim_label": claim_label,
        "unknown_projects": context_payload["unknown_projects"],
    }
    telemetry_sources_payload = {
        "version": 1,
        "generated_at": now_iso(),
        "sources": telemetry_sources,
    }

    write_json(CONTEXT_SAVINGS_PATH, context_payload)
    write_json(TOKEN_SAVINGS_PATH, token_payload)
    write_json(LATENCY_METRICS_PATH, latency_payload)
    write_json(TELEMETRY_SOURCES_PATH, telemetry_sources_payload)
    return {
        "projects_index": projects_index,
        "context": context_payload,
        "token": token_payload,
        "latency": latency_payload,
        "telemetry_sources": telemetry_sources_payload,
    }


def issue(severity: str, scope: str, check: str, message: str) -> dict[str, str]:
    return {
        "severity": severity,
        "scope": scope,
        "check": check,
        "message": message,
    }


def merge_state(issues: list[dict[str, str]]) -> str:
    severities = {item["severity"] for item in issues}
    if "needs_attention" in severities:
        return "needs_attention"
    if "warning" in severities:
        return "warning"
    return "healthy"


def run_health_check() -> dict[str, Any]:
    if not PROJECTS_INDEX_PATH.exists() or not CONTEXT_SAVINGS_PATH.exists() or not TELEMETRY_SOURCES_PATH.exists():
        refresh_global_metrics()

    projects_index = read_json(PROJECTS_INDEX_PATH, {"projects": []})
    context = read_json(CONTEXT_SAVINGS_PATH, {})
    telemetry_sources = read_json(TELEMETRY_SOURCES_PATH, {"sources": []})

    issues: list[dict[str, str]] = []
    checks: list[dict[str, Any]] = []

    canonical_checks = {
        "boot_files": [
            BASE / "boot" / "boot_summary.json",
            BASE / "boot" / "user_defaults.json",
            BASE / "boot" / "project_registry.json",
        ],
        "memory_files": [
            BASE / "user_preferences.json",
            BASE / "store" / "global_records.jsonl",
            BASE / "indexes" / "by_project.json",
        ],
        "compaction": [
            BASE / "compaction_report.json",
            BASE / "scripts" / "compact.py",
        ],
        "cost_optimizer": [
            repo_cost_dir(BASE) / "optimizer_config.yaml",
            repo_cost_dir(BASE) / "packet_budget_status.json",
            repo_cost_dir(BASE) / "latest_optimization_report.md",
        ],
        "task_memory": [
            repo_task_memory_dir(BASE) / "task_memory_status.json",
            repo_task_memory_dir(BASE) / "task_taxonomy.json",
            repo_task_memory_dir(BASE) / "task_resolution_rules.md",
            repo_task_memory_dir(BASE) / "unknown" / "records.jsonl",
        ],
        "failure_memory": [
            repo_failure_memory_dir(BASE) / "index.json",
            repo_failure_memory_dir(BASE) / "failure_memory_status.json",
            repo_failure_memory_dir(BASE) / "summaries" / "common_patterns.md",
        ],
        "memory_graph": [
            repo_memory_graph_dir(BASE) / "graph_status.json",
            repo_memory_graph_dir(BASE) / "nodes" / "nodes.jsonl",
            repo_memory_graph_dir(BASE) / "edges" / "edges.jsonl",
            repo_memory_graph_dir(BASE) / "snapshots" / "latest_graph_snapshot.json",
        ],
        "knowledge_library": [
            BASE / ".ai_context_engine" / "state.json",
            repo_metrics_dir(BASE) / "weekly_summary.json",
            repo_library_dir(BASE) / "registry.json",
            repo_library_dir(BASE) / "retrieval_status.json",
        ],
    }
    for check_name, paths in canonical_checks.items():
        missing = [rel(path) for path in paths if not path.exists()]
        if missing:
            issues.append(issue("needs_attention", CANONICAL_SCOPE, check_name, f"Missing canonical files: {', '.join(missing)}"))
        checks.append({
            "scope": CANONICAL_SCOPE,
            "check": check_name,
            "status": "healthy" if not missing else "needs_attention",
            "missing": missing,
        })

    project_names = {row["name"] for row in projects_index.get("projects", [])}
    source_names = {row["project"] for row in telemetry_sources.get("sources", [])}
    if project_names != source_names:
        issues.append(issue("warning", "global_metrics", "consistency", "projects_index.json and telemetry_sources.json are out of sync"))
    checks.append({
        "scope": "global_metrics",
        "check": "consistency",
        "status": "healthy" if project_names == source_names else "warning",
        "projects_index_count": len(project_names),
        "telemetry_sources_count": len(source_names),
    })

    for row in projects_index.get("projects", []):
        repo = Path(row["repo_path"])
        compat = repo_memory_dir(repo)
        agents = repo / "AGENTS.md"
        weekly = repo_metrics_dir(repo) / "weekly_summary.json"
        state_path = repo_engine_dir(repo) / "state.json"
        capability_version = normalize_engine_capability_version(
            row.get("engine_capability_version"),
            legacy_iteration=row.get("installed_iteration"),
        )
        repo_issues: list[dict[str, str]] = []
        if not compat.exists():
            if capability_at_least(capability_version, 2) or state_path.exists():
                repo_issues.append(issue("warning", row["name"], "memory_availability", "Missing .ai_context_engine/memory bootstrap layer"))
        else:
            derived = compat / "derived_boot_summary.json"
            if not derived.exists():
                repo_issues.append(issue("needs_attention", row["name"], "bootstrap", "Missing .ai_context_engine/memory/derived_boot_summary.json"))
        if capability_at_least(capability_version, MIN_CAPABILITY_COST_OPTIMIZER) and not (repo_cost_dir(repo) / "packet_budget_status.json").exists():
            repo_issues.append(issue("needs_attention", row["name"], "cost_optimizer", "Missing canonical .ai_context_engine/cost/packet_budget_status.json"))
        if capability_at_least(capability_version, MIN_CAPABILITY_TASK_MEMORY) and not (repo_task_memory_dir(repo) / "task_memory_status.json").exists():
            repo_issues.append(issue("needs_attention", row["name"], "task_memory", "Missing canonical .ai_context_engine/task_memory/task_memory_status.json"))
        if capability_at_least(capability_version, MIN_CAPABILITY_FAILURE_MEMORY) and not (repo_failure_memory_dir(repo) / "failure_memory_status.json").exists():
            repo_issues.append(issue("needs_attention", row["name"], "failure_memory", "Missing canonical .ai_context_engine/failure_memory/failure_memory_status.json"))
        if capability_at_least(capability_version, MIN_CAPABILITY_MEMORY_GRAPH) and not (repo_memory_graph_dir(repo) / "graph_status.json").exists():
            repo_issues.append(issue("needs_attention", row["name"], "memory_graph", "Missing canonical .ai_context_engine/memory_graph/graph_status.json"))
        consistency = runtime_consistency_report(repo)
        if not state_path.exists():
            repo_issues.append(issue("warning", row["name"], "runtime_state", "Missing .ai_context_engine/state.json"))
        else:
            state = read_json(state_path, {})
            if not bool(state.get("adapter_runtime_enabled")):
                repo_issues.append(issue("warning", row["name"], "runtime_integration", "Adapter runtime is not marked as enabled"))
            if str(state.get("runner_integration_status", "") or "") not in {"wrapper_ready", "hook_ready", "active", "native_ready"}:
                repo_issues.append(issue("warning", row["name"], "runtime_integration", "Runner integration status is not ready"))
            if not str(state.get("auto_execution_entrypoint", "") or "").strip():
                repo_issues.append(issue("warning", row["name"], "runtime_integration", "Missing auto execution entrypoint in runtime state"))
            if not (repo / "AGENTS.override.md").exists():
                repo_issues.append(issue("warning", row["name"], "runtime_integration", "Missing Codex native repo file AGENTS.override.md"))
            if not (repo / "CLAUDE.md").exists():
                repo_issues.append(issue("warning", row["name"], "runtime_integration", "Missing Claude native repo file CLAUDE.md"))
            if not (repo / ".claude" / "settings.json").exists():
                repo_issues.append(issue("warning", row["name"], "runtime_integration", "Missing Claude native project hooks .claude/settings.json"))
        if consistency.get("status") == "warning":
            repo_issues.append(issue("warning", row["name"], "runtime_consistency", "Repo runtime state disagrees with effective communication policy"))
        elif consistency.get("status") == "not_initialized":
            message = "Repo runtime consistency could not be verified because initialization is incomplete"
            if capability_version in {None, 1}:
                message = "Repo runtime consistency is not initialized yet"
            repo_issues.append(issue("warning", row["name"], "runtime_consistency", message))
        if not agents.exists():
            repo_issues.append(issue("warning", row["name"], "bootstrap", "Missing AGENTS.md instructions"))
        if row.get("telemetry_dir") != "unknown" and not weekly.exists():
            repo_issues.append(issue("warning", row["name"], "telemetry_activity", "Missing .ai_context_engine/metrics/weekly_summary.json"))
        checks.append({
            "scope": row["name"],
            "check": "project_health",
            "status": merge_state(repo_issues),
            "issues": repo_issues,
            "consistency": consistency,
        })
        issues.extend(repo_issues)

    if not context.get("project_breakdown"):
        issues.append(issue("warning", "global_metrics", "aggregation", "No project breakdown available in global context savings payload"))

    health = {
        "version": 1,
        "generated_at": now_iso(),
        "state": merge_state(issues),
        "checks": checks,
        "issues": issues,
        "summary": {
            "projects_detected": len(projects_index.get("projects", [])),
            "projects_with_telemetry": int(context.get("projects_with_telemetry", 0) or 0),
            "projects_with_memory": int(context.get("projects_with_memory", 0) or 0),
            "global_metrics_dir": rel(GLOBAL_DIR),
        },
    }
    write_json(HEALTH_REPORT_PATH, health)
    return health


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Aggregate AI Context Engine telemetry across repositories.")
    parser.add_argument("--refresh", action="store_true", help="Refresh projects index and global savings artifacts.")
    parser.add_argument("--health-check", action="store_true", help="Run AI Context Engine global health checks.")
    parser.add_argument("--json", action="store_true", help="Print full JSON output for the requested action.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.refresh and not args.health_check:
        args.refresh = True
    payload: dict[str, Any] = {}
    if args.refresh:
        payload["refresh"] = refresh_global_metrics()
    if args.health_check:
        payload["health_check"] = run_health_check()
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(json.dumps({
            "global_metrics_dir": rel(GLOBAL_DIR),
            "refreshed": bool(args.refresh),
            "health_checked": bool(args.health_check),
        }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
